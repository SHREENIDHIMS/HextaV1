"""Indexing — write document chunks to Postgres.

Writes both metadata rows (document_chunks content, section, etc.) and
vector embeddings to the document_chunks table. Handles deduplication
via content_hash.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from psycopg import Connection

from app.db.postgres.models import content_hash
from app.documents.chunking.structural_chunker import Chunk

logger = logging.getLogger(__name__)


@dataclass
class IndexResult:
    document_id: int
    chunks_indexed: int
    chunks_skipped: int  # duplicates


def index_document(
    conn: Connection,
    doc_title: str,
    doc_type: str,
    department: str,
    source_path: str | None,
    chunks: Sequence[Chunk],
    embeddings: Sequence[list[float]] | None = None,
) -> IndexResult:
    """Insert a document and its chunks into Postgres.

    Assumes the schema has already been created (ensure_schema()).
    """
    if embeddings is not None and len(embeddings) != len(chunks):
        raise ValueError(
            f"embeddings length {len(embeddings)} does not match chunks length {len(chunks)}"
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (title, doc_type, department, source_path)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (doc_title, doc_type, department, source_path),
        )
        document_id = cur.fetchone()["id"]
        logger.info("Indexing document '%s' (id=%d)", doc_title, document_id)

    indexed = 0
    skipped = 0
    seen_hashes: set[str] = set()

    for i, chunk in enumerate(chunks):
        ch = content_hash(chunk.content)
        if ch in seen_hashes:
            skipped += 1
            continue
        seen_hashes.add(ch)

        embedding = (
            embeddings[i] if embeddings else None
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO document_chunks
                    (document_id, content, content_hash, embedding,
                     section, chunk_type, department)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (content_hash) DO NOTHING
                """,
                (
                    document_id,
                    chunk.content,
                    ch,
                    embedding,
                    chunk.section,
                    chunk.chunk_type,
                    department,
                ),
            )
            if cur.rowcount > 0:
                indexed += 1
            else:
                skipped += 1

    # A re-ingest whose every chunk is a duplicate would leave an orphan
    # documents row with zero chunks behind. Remove it so the doc table only
    # ever lists documents that actually contribute chunks (I9).
    if indexed == 0 and skipped > 0:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
        conn.commit()
        logger.info(
            "Document %d was a full duplicate (%d chunks skipped); removed orphan row",
            document_id,
            skipped,
        )
        return IndexResult(document_id, 0, skipped)

    conn.commit()
    logger.info("Document %d: %d chunks indexed, %d skipped", document_id, indexed, skipped)
    return IndexResult(document_id, indexed, skipped)
