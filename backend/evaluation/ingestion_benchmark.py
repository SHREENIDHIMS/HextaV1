"""Benchmark for the document upload + ingestion pipeline.

Measures per-stage latency (validation, text extraction, chunking,
embedding generation, indexing) and end-to-end throughput for a batch
of documents. Results are written to evaluation/reports/.

Usage:
    python -m evaluation.ingestion_benchmark --output-dir evaluation/reports
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.db.postgres.schema import ensure_schema
from app.db.postgres.session import acquire
from app.documents.chunking.structural_chunker import StructuralChunker
from app.documents.embedding import generate_embeddings
from app.documents.entity_extraction import extract_entities
from app.documents.indexing import index_document
from app.documents.metadata_extraction import extract_metadata
from app.documents.text_extraction import ExtractedText, extract_text
from app.documents.validation import validate_upload


def _sample_documents() -> list[tuple[str, str]]:
    """Return (filename, content) pairs for benchmark documents."""
    return [
        (
            "credit_score_policy.txt",
            "CREDIT SCORE REQUIREMENTS\n\n"
            "The minimum credit score for conventional loans is 620.\n"
            "For FHA loans, the minimum is 580 with 3.5% down.\n"
            "VA loans require a minimum credit score of 500.\n\n"
            "Borrowers with scores below these minimums must provide\n"
            "a larger down payment and may need a co-signer.\n\n"
            "Credit scores are calculated from the following factors:\n"
            "1. Payment history (35%)\n"
            "2. Credit utilization (30%)\n"
            "3. Length of credit history (15%)\n"
            "4. New credit inquiries (10%)\n"
            "5. Credit mix (10%)\n",
        ),
        (
            "dti_ratio.txt",
            "DEBT-TO-INCOME (DTI) RATIO\n\n"
            "The DTI ratio is calculated by dividing total monthly debt\n"
            "by gross monthly income.\n\n"
            "Maximum DTI limits:\n"
            "- FHA: 43% (can go to 50% with compensating factors)\n"
            "- Conventional: 43% (max 45% with strong credit)\n"
            "- VA: 41% (can be higher with residual income)\n"
            "- USDA: 29% front-end, can go higher with back-end analysis\n",
        ),
        (
            "closing_costs.md",
            "# Closing Costs Overview\n\n"
            "Typical closing costs range from 2% to 5% of the loan amount.\n\n"
            "| Fee | Low | High |\n"
            "|-----|-----|------|\n"
            "| Origination | 0.5% | 1.5% |\n"
            "| Appraisal | $300 | $900 |\n"
            "| Title | 0.5% | 1.0% |\n",
        ),
    ]


def run_ingestion_benchmark(output_dir: str) -> dict:
    """Run the ingestion benchmark and return results."""
    docs = _sample_documents()

    results: list[dict] = []
    per_stage: dict[str, list[float]] = {
        "validation": [],
        "extraction": [],
        "metadata": [],
        "entities": [],
        "chunking": [],
        "embedding": [],
        "indexing": [],
    }

    ensure_schema()

    for filename, content in docs:
        path = Path("storage/pending") / f"bench_{uuid.uuid4().hex[:8]}_{filename}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        start = time.perf_counter()

        # Stage 1: validation
        t0 = time.perf_counter()
        vresult = validate_upload(filename, len(content.encode("utf-8")))
        per_stage["validation"].append((time.perf_counter() - t0) * 1000)

        assert vresult.valid, f"Validation failed: {vresult.error}"

        # Stage 2: text extraction
        t0 = time.perf_counter()
        extracted = extract_text(path)
        per_stage["extraction"].append((time.perf_counter() - t0) * 1000)

        # Stage 3: metadata
        t0 = time.perf_counter()
        metadata = extract_metadata(extracted, path)
        per_stage["metadata"].append((time.perf_counter() - t0) * 1000)

        # Stage 4: entities
        t0 = time.perf_counter()
        entities = extract_entities(extracted.text)
        per_stage["entities"].append((time.perf_counter() - t0) * 1000)

        # Stage 5: chunking
        t0 = time.perf_counter()
        chunker = StructuralChunker(max_tokens=settings.max_excerpt_chars // 2)
        chunks = list(chunker.chunk(extracted))
        per_stage["chunking"].append((time.perf_counter() - t0) * 1000)

        # Stage 6: embedding
        t0 = time.perf_counter()
        chunk_texts = [c.content for c in chunks]
        embeddings = generate_embeddings(chunk_texts)
        per_stage["embedding"].append((time.perf_counter() - t0) * 1000)

        # Stage 7: indexing
        t0 = time.perf_counter()
        with acquire() as conn:
            idx_result = index_document(
                conn=conn,
                doc_title=metadata.title,
                doc_type=metadata.doc_type,
                department=metadata.department,
                source_path=metadata.source_path,
                chunks=chunks,
                embeddings=embeddings,
            )
        per_stage["indexing"].append((time.perf_counter() - t0) * 1000)

        elapsed_ms = (time.perf_counter() - start) * 1000
        results.append({
            "filename": filename,
            "doc_id": idx_result.document_id,
            "chunks_indexed": idx_result.chunks_indexed,
            "chunks_skipped": idx_result.chunks_skipped,
            "total_ms": round(elapsed_ms, 1),
            "department": metadata.department,
            "doc_type": metadata.doc_type,
        })
        path.unlink(missing_ok=True)

    # Build summary
    summary = {}
    for stage, times in per_stage.items():
        if times:
            summary[stage] = {
                "p50": round(statistics.median(times), 1),
                "p95": round(sorted(times)[int(len(times) * 0.95) - 1], 1) if len(times) > 1 else round(times[0], 1),
                "min": round(min(times), 1),
                "max": round(max(times), 1),
            }

    report = {
        "timestamp": datetime.now().isoformat(),
        "documents": len(docs),
        "total_ms": round(sum(r["total_ms"] for r in results), 1),
        "per_document": results,
        "per_stage_ms": summary,
        "stages": {stage: round(sum(times) / len(times), 1) for stage, times in per_stage.items()},
    }

    # Save report
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    fname = out / f"ingestion_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(fname, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to {fname}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Document ingestion pipeline benchmark")
    parser.add_argument("--output-dir", default="evaluation/reports")
    args = parser.parse_args()

    print("Starting ingestion benchmark...")
    report = run_ingestion_benchmark(args.output_dir)
    print(json.dumps(report, indent=2))
