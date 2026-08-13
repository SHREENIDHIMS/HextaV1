"""Document ingestion batch pipeline — entry point.

Runs as a standalone process (invoked via infra/scripts/run_ingestion.sh),
NOT inside the FastAPI request handler. Loads the embedding model,
processes files in storage/pending/, and writes indexed chunks to Postgres.

Pipeline order (per SKILL.md Phase 2):
  validation → text_extraction → structural_chunker →
  metadata_extraction → entity_extraction (light) →
  embedding → indexing

Outcomes (Phase 3 hardening):
  - PROCESSED   → file moved to storage/processed
  - QUARANTINED → permanent failure (unreadable/scanned-without-OCR) →
                  moved to storage/quarantine so it stops failing every batch
  - FAILED      → transient failure (exception) → left in storage/pending to
                  be retried on the next batch run
One file's failure never aborts the batch (I1).

Usage:
    python -m app.documents.ingest_batch --queue-dir /path/to/pending
"""

from __future__ import annotations

import argparse
import enum
import logging
import time
from pathlib import Path

from app.config import settings
from app.db.postgres.schema import ensure_schema
from app.db.postgres.session import acquire
from app.documents.chunking.structural_chunker import StructuralChunker
from app.documents.embedding import generate_embeddings
from app.documents.entity_extraction import extract_entities
from app.documents.indexing import index_document
from app.documents.metadata_extraction import extract_metadata
from app.documents.text_extraction import extract_text

logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Embedding generation is retried a couple of times before a file is failed
# (I5) — the model load is a one-time cost and transient failures are common
# on a cold micro-tier box.
EMBEDDING_ATTEMPTS = 2


class IngestOutcome(str, enum.Enum):
    PROCESSED = "processed"
    QUARANTINED = "quarantined"
    FAILED = "failed"


def _move_file(file_path: Path, target_dir: str) -> Path:
    """Move a file into target_dir, surviving name collisions (I7).

    The destination is disambiguated when a file with the same name already
    exists. Existence is checked explicitly rather than catching
    FileExistsError: POSIX Path.rename() silently overwrites (no exception),
    so exception-based collision handling only ever worked on Windows — and
    failed on CI's ubuntu runners.
    """
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    dest = target / file_path.name
    if dest.exists():
        # Same-second collisions between two files sharing a stem would
        # otherwise produce the identical disambiguated name — bump the
        # suffix until a free one is found.
        n = 0
        while True:
            candidate = target / f"{file_path.stem}-{int(time.time())}-{n}{file_path.suffix}"
            if not candidate.exists():
                dest = candidate
                break
            n += 1
    file_path.rename(dest)
    logger.info("Moved %s → %s", file_path, dest)
    return dest


def _move_to_processed(file_path: Path) -> None:
    _move_file(file_path, settings.storage_processed_dir)


def _move_to_quarantine(file_path: Path) -> None:
    logger.error("Quarantining permanent-failure file: %s", file_path.name)
    _move_file(file_path, settings.storage_quarantine_dir)


def process_file(file_path: Path) -> IngestOutcome:
    """Process a single document file through the full pipeline.

    Never raises — every failure is contained and reported via the returned
    outcome (I1). Extraction of empty text (e.g. a scanned PDF with no OCR)
    is a permanent failure and quarantines the file (I3).
    """
    logger.info("Processing: %s", file_path.name)

    try:
        extracted = extract_text(file_path)
    except Exception as e:
        logger.error("Text extraction failed for %s: %s", file_path.name, e)
        return IngestOutcome.FAILED

    if not extracted.text.strip():
        logger.error("No text extracted from %s — quarantining", file_path.name)
        return IngestOutcome.QUARANTINED

    try:
        metadata = extract_metadata(extracted, file_path)
        entities = extract_entities(extracted.text)
        logger.info(
            "Metadata: title=%s, type=%s, %d lenders, %d products%s",
            metadata.title,
            metadata.doc_type,
            len(entities.lenders),
            len(entities.products),
            " (OCR)" if extracted.ocr_applied else "",
        )

        chunker = StructuralChunker(max_tokens=settings.chunk_max_tokens)
        chunks = list(chunker.chunk(extracted))
        if not chunks:
            logger.warning("No chunks produced for %s", file_path.name)
            return IngestOutcome.QUARANTINED

        logger.info("Produced %d chunks", len(chunks))

        embeddings: list[list[float]] | None = None
        if settings.embedding_enabled:
            embeddings = _generate_embeddings_with_retry(
                chunks=[c.content for c in chunks],
                file_name=file_path.name,
            )

        with acquire() as conn:
            result = index_document(
                conn=conn,
                doc_title=metadata.title,
                doc_type=metadata.doc_type,
                department=metadata.department,
                source_path=metadata.source_path,
                chunks=chunks,
                embeddings=embeddings,
            )
            logger.info(
                "Indexed %d, skipped %d for document %d",
                result.chunks_indexed,
                result.chunks_skipped,
                result.document_id,
            )
    except Exception:
        logger.exception("Unexpected failure processing %s", file_path.name)
        return IngestOutcome.FAILED

    return IngestOutcome.PROCESSED


def _generate_embeddings_with_retry(
    chunks: list[str], file_name: str
) -> list[list[float]]:
    """Generate embeddings with a bounded retry.

    A failure after retries FAILS the file (leaves it in pending) instead of
    silently indexing NULL-embedding chunks that can never be found by vector
    search (I5). The operator sees the failure in the log and the file stays
    queued for the next run.
    """
    last_error: Exception | None = None
    for attempt in range(1, EMBEDDING_ATTEMPTS + 1):
        try:
            return generate_embeddings(chunks)
        except Exception as e:
            last_error = e
            if attempt < EMBEDDING_ATTEMPTS:
                logger.warning(
                    "Embedding generation failed for %s (attempt %d/%d): %s — retrying",
                    file_name,
                    attempt,
                    EMBEDDING_ATTEMPTS,
                    e,
                )
                time.sleep(2 * attempt)
    assert last_error is not None
    raise RuntimeError(
        f"Embedding generation failed for {file_name} after "
        f"{EMBEDDING_ATTEMPTS} attempts: {last_error}"
    ) from last_error


def main(queue_dir: str) -> None:
    """Process all files in the queue directory."""
    queue_path = Path(queue_dir)
    if not queue_path.exists():
        logger.error("Queue directory does not exist: %s", queue_path)
        return

    files = [
        f for f in queue_path.iterdir()
        if f.is_file() and f.suffix.lower() in {".pdf", ".txt", ".docx", ".html", ".md"}
    ]
    if not files:
        logger.info("No files to process in %s", queue_path)
        return

    ensure_schema()

    counts = {outcome: 0 for outcome in IngestOutcome}
    for file_path in files:
        # Belt-and-suspenders isolation (I1): process_file itself never raises,
        # but a defensive guard here guarantees one bad file can't kill the batch.
        try:
            outcome = process_file(file_path)
        except Exception:
            logger.exception("Unhandled error in process_file for %s", file_path.name)
            outcome = IngestOutcome.FAILED

        counts[outcome] += 1
        if outcome == IngestOutcome.PROCESSED:
            _move_to_processed(file_path)
        elif outcome == IngestOutcome.QUARANTINED:
            _move_to_quarantine(file_path)
        # FAILED: intentionally left in the pending queue for the next run.

    logger.info(
        "Batch complete: %d processed, %d quarantined, %d failed",
        counts[IngestOutcome.PROCESSED],
        counts[IngestOutcome.QUARANTINED],
        counts[IngestOutcome.FAILED],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Document ingestion batch pipeline")
    parser.add_argument(
        "--queue-dir",
        default=settings.storage_pending_dir,
        help="Directory to scan for pending documents",
    )
    args = parser.parse_args()
    main(args.queue_dir)
