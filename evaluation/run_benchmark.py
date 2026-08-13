"""Evaluation benchmark runner.

Runs the full query-processing pipeline against the eval dataset and
measures retrieval accuracy (precision, recall, MRR, nDCG, hit rate)
and latency. Results are written to evaluation/reports/<timestamp>.json.

Two phases:
  * query processing (DB-free): sub-question split, intent, entity,
    spell-correction accuracy and per-query latency.
  * retrieval (DB-backed): runs the REAL serving path
    (process_query -> search_knowledge_base -> RRF) for each dataset item
    that carries a ``gold_phrase`` and measures precision@k / recall@k /
    MRR@10 / nDCG@10 / hit_rate@10 against the gold chunk located by
    phrase at runtime.

Per CLAUDE.md rule 7, ranking-weight / confidence-threshold changes must
be backed by a run of this benchmark.

Usage:
    python -m evaluation.run_benchmark --output-dir evaluation/reports
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend/app is importable
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Load backend/.env into os.environ WITHOUT chdir so relative paths stay
# repo-root-relative and pydantic env_file lookups fall back to the env
# vars set here (mirrors evaluation/retrieval_benchmark.py).
_envpath = backend_path / ".env"
if _envpath.is_file():
    for _line in _envpath.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

from evaluation.datasets.eval_questions import load_dataset
from evaluation.metrics.precision_recall import precision_at_k, recall_at_k
from evaluation.metrics.mrr import mean_reciprocal_rank
from evaluation.metrics.ndcg import ndcg_at_k
from evaluation.metrics.hit_rate import hit_rate

ADMIN_USER = {"role": "super_admin", "department": "general"}
RETRIEVAL_CUTOFFS = (1, 5, 10)


def _locate_gold_chunk(conn, phrase: str) -> tuple[int | None, str | None]:
    """Locate the chunk containing the verbatim gold phrase (runtime gold).

    Whitespace is normalized on both sides so single-space gold phrases
    still match chunked/OCR'd paragraphs.
    """
    needle = " ".join(phrase.lower().split())
    with conn.cursor() as cur:
        cur.execute(
            "SELECT c.id, d.title FROM document_chunks c "
            "JOIN documents d ON d.id = c.document_id "
            "WHERE POSITION(%s IN regexp_replace(LOWER(c.content), '\\s+', ' ', 'g')) > 0 "
            "ORDER BY c.id LIMIT 1",
            (needle,),
        )
        row = cur.fetchone()
    if row is None:
        return None, None
    return row["id"], row["title"]


def _run_retrieval(dataset: list[dict]) -> dict:
    """Run real retrieval per gold item and aggregate rank metrics."""
    gold_items = [item for item in dataset if item.get("gold_phrase")]

    try:
        from app.db.postgres.session import acquire
        from app.query_processing.pipeline import process_query
        from app.ranking.rrf import rank_fusion
        from app.search.hybrid_orchestrator import search_knowledge_base
    except Exception as exc:  # pragma: no cover - import guard
        return {
            "available": False,
            "error": f"backend import failed: {exc}",
            "gold_items": len(gold_items),
        }

    per_query = []
    rank_lists: list[list[int]] = []
    relevant_sets: list[set[int]] = []
    relevance_scores_list: list[dict[int, float]] = []
    found = 0

    try:
        with acquire() as conn:
            for item in gold_items:
                plan = process_query(item["question"])
                sub_query_texts = [sq.expanded for sq in plan.sub_queries] or [item["question"]]

                result = search_knowledge_base(
                    conn=conn,
                    sub_queries=sub_query_texts,
                    user=ADMIN_USER,
                )

                chunk_lookup = {c.chunk_id: c.__dict__ for c in result.candidates}
                bm25_ranked = sorted(
                    ((c.chunk_id, c.bm25_score) for c in result.candidates),
                    key=lambda x: x[1], reverse=True,
                )
                vector_ranked = sorted(
                    ((c.chunk_id, c.vec_score) for c in result.candidates),
                    key=lambda x: x[1], reverse=True,
                )
                ranked = rank_fusion(bm25_ranked, vector_ranked, chunk_lookup)
                retrieved_ids = [c.chunk_id for c in ranked]

                gold_chunk_id, gold_doc = _locate_gold_chunk(conn, item["gold_phrase"])
                relevant = {gold_chunk_id} if gold_chunk_id is not None else set()
                found += int(bool(relevant))

                rank_lists.append(retrieved_ids)
                relevant_sets.append(relevant)
                relevance_scores_list.append({gold_chunk_id: 1.0} if gold_chunk_id is not None else {})

                per_query.append({
                    "id": item["id"],
                    "question": item["question"],
                    "gold_phrase": item["gold_phrase"],
                    "expected_doc_title": item.get("expected_doc_title"),
                    "gold_chunk_id": gold_chunk_id,
                    "gold_doc_title": gold_doc,
                    "retrieved_count": len(retrieved_ids),
                    "hits": {
                        f"recall@{k}": recall_at_k(retrieved_ids, relevant, k)
                        for k in RETRIEVAL_CUTOFFS
                    },
                    "precision": {
                        f"precision@{k}": precision_at_k(retrieved_ids, relevant, k)
                        for k in RETRIEVAL_CUTOFFS
                    },
                    "ndcg_10": ndcg_at_k(retrieved_ids, relevance_scores_list[-1], 10),
                    "rank": (
                        retrieved_ids.index(gold_chunk_id) + 1
                        if gold_chunk_id is not None and gold_chunk_id in retrieved_ids else 0
                    ),
                })
    except Exception as exc:  # pragma: no cover - DB down
        return {
            "available": False,
            "error": f"retrieval phase failed: {exc}",
            "gold_items": len(gold_items),
            "queries": per_query,
        }

    n = len(per_query)
    n_found = found

    def _mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    return {
        "available": True,
        "gold_items": len(gold_items),
        "gold_found": n_found,
        "gold_not_found_ids": [
            q["id"] for q in per_query if q["gold_chunk_id"] is None
        ],
        "precision_at_1": _mean([q["precision"]["precision@1"] for q in per_query]),
        "precision_at_5": _mean([q["precision"]["precision@5"] for q in per_query]),
        "precision_at_10": _mean([q["precision"]["precision@10"] for q in per_query]),
        "recall_at_1": _mean([q["hits"]["recall@1"] for q in per_query]),
        "recall_at_5": _mean([q["hits"]["recall@5"] for q in per_query]),
        "recall_at_10": _mean([q["hits"]["recall@10"] for q in per_query]),
        "mrr_10": round(mean_reciprocal_rank(rank_lists, relevant_sets), 4),
        "ndcg_10": round(sum(ndcg_at_k(ids, scores, 10) for ids, scores in zip(rank_lists, relevance_scores_list)) / n, 4) if n else 0.0,
        "hit_rate_10": round(hit_rate(rank_lists, relevant_sets, k=10), 4),
        "queries": per_query,
    }


def run_benchmark(output_dir: str = "evaluation/reports") -> dict:
    """Run the benchmark and return results dict."""
    dataset = load_dataset()

    # Import pipeline (pure function, no DB)
    from app.query_processing import pipeline

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_size": len(dataset),
        "queries": [],
    }

    for item in dataset:
        query_start = time.perf_counter()
        plan = pipeline.process_query(item["question"])
        query_latency = (time.perf_counter() - query_start) * 1000

        sub_query_count = len(plan.sub_queries)

        # Spell correction check
        spell_corrected = False
        if plan.sub_queries:
            first_sq = plan.sub_queries[0]
            if first_sq.text != plan.normalized.split(",")[0].strip(" ?!;").strip():
                spell_corrected = True

        # Intent: matched if the set of observed sub-query intents is a
        # subset of the expected intents (multi-intent items carry several).
        expected_intents = set(item.get("expected_intents") or [])
        observed_intents = {sq.intent for sq in plan.sub_queries}
        intent_ok = bool(expected_intents) and observed_intents <= expected_intents

        # Entities: every expected canonical entity must be extracted.
        entities_ok = True
        expected_entities = set(item.get("expected_entities") or [])
        if expected_entities:
            all_entities = {e.canonical for sq in plan.sub_queries for e in sq.entities}
            entities_ok = expected_entities <= all_entities

        # Multi-question check
        sub_questions_ok = sub_query_count == item.get("expected_sub_questions", 1)

        result = {
            "id": item["id"],
            "question": item["question"],
            "sub_queries": sub_query_count,
            "sub_question_ok": sub_questions_ok,
            "intent": sorted(observed_intents),
            "expected_intents": sorted(expected_intents),
            "intent_ok": intent_ok,
            "entities": sorted({e.canonical for sq in plan.sub_queries for e in sq.entities}),
            "expected_entities": sorted(expected_entities),
            "entities_ok": entities_ok,
            "spell_corrected": spell_corrected,
            "latency_ms": round(query_latency, 2),
            "normalized": plan.normalized,
            "truncated": plan.truncated,
        }

        results["queries"].append(result)

    # Aggregate query-processing metrics
    correct_sub_questions = sum(1 for q in results["queries"] if q["sub_question_ok"])
    correct_intents = sum(1 for q in results["queries"] if q["intent_ok"])
    correct_entities = sum(1 for q in results["queries"] if q["entities_ok"])
    total_queries = len(results["queries"])
    total_elapsed_ms = sum(q["latency_ms"] for q in results["queries"])

    results["summary"] = {
        "sub_question_accuracy": correct_sub_questions / total_queries if total_queries else 0.0,
        "intent_accuracy": correct_intents / total_queries if total_queries else 0.0,
        "entity_accuracy": correct_entities / total_queries if total_queries else 0.0,
        "avg_query_processing_latency_ms": round(total_elapsed_ms / total_queries, 2) if total_queries else 0.0,
        "total_latency_ms": round(total_elapsed_ms, 2),
    }

    # Retrieval phase (rule-7 gate: ranking quality)
    retrieval = _run_retrieval(dataset)
    results["retrieval"] = {
        key: value for key, value in retrieval.items() if key != "queries"
    }
    if retrieval.get("queries"):
        results["retrieval"]["queries"] = retrieval["queries"]

    # Write report
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"benchmark_{timestamp}.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    results["report_path"] = report_path

    return results


def main():
    parser = argparse.ArgumentParser(description="Run Hexta evaluation benchmark")
    parser.add_argument("--output-dir", default="evaluation/reports", help="Directory for output reports")
    parser.add_argument("--backend-path", default=None, help="Path to backend directory")
    args = parser.parse_args()

    if args.backend_path:
        backend = Path(args.backend_path).resolve()
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))

    print(f"Starting benchmark at {datetime.now(timezone.utc).isoformat()}")
    results = run_benchmark(args.output_dir)
    summary = results["summary"]
    retrieval = results["retrieval"]

    print(f"\n{'='*60}")
    print(f"Benchmark Results: {results['dataset_size']} queries")
    print(f"{'='*60}")
    print(f"  Sub-question accuracy:  {summary['sub_question_accuracy']:.1%}")
    print(f"  Intent accuracy:        {summary['intent_accuracy']:.1%}")
    print(f"  Entity accuracy:        {summary['entity_accuracy']:.1%}")
    print(f"  Avg query proc latency: {summary['avg_query_processing_latency_ms']:.1f}ms")
    print(f"  Total latency:          {summary['total_latency_ms']:.1f}ms")

    if retrieval.get("available"):
        print(f"\n  Retrieval (gold items: {retrieval['gold_items']}, found: {retrieval['gold_found']}):")
        print(f"    precision@1: {retrieval['precision_at_1']:.3f}  @5: {retrieval['precision_at_5']:.3f}  @10: {retrieval['precision_at_10']:.3f}")
        print(f"    recall@1:    {retrieval['recall_at_1']:.3f}  @5: {retrieval['recall_at_5']:.3f}  @10: {retrieval['recall_at_10']:.3f}")
        print(f"    MRR@10: {retrieval['mrr_10']:.3f}  nDCG@10: {retrieval['ndcg_10']:.3f}  hit_rate@10: {retrieval['hit_rate_10']:.3f}")
        if retrieval["gold_not_found_ids"]:
            print(f"    gold phrases not found in KB (ids): {retrieval['gold_not_found_ids']}")
    else:
        print(f"\n  Retrieval unavailable: {retrieval.get('error', 'unknown')}")

    print(f"\n  Report: {results['report_path']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
