"""Retrieval accuracy + reranker validation benchmark.

Runs the REAL search pipeline against the knowledge base:

    process_query -> hybrid BM25 + pgvector SQL (single statement,
    RBAC in the WHERE clause) -> RRF rank fusion -> optional reranker.

Per CLAUDE.md rule 6/7 this produces three things in one report:

  * recall@K / MRR@10 / retrieval-rate — measured on the current serving
    configuration (rerank ON when ``HEXA_RERANK_ENABLED=true``, else off).
  * an AND-vs-OR tsquery ablation — the OR tsquery is current serving
    behaviour; the AND tsquery reproduces the pre-fix "all query terms must
    co-occur" behaviour, isolating the recall effect of the bm25_search
    ``&& -> ||`` change (rerank OFF in both arms).
  * a rerank-on-vs-rerank-off delta — same candidate set, reranker applied
    or not, isolating the reranker's ranking effect.
  * an isolated reranker p95 latency gate (<200ms, rule #6) when the
    cross-encoder model is present.

Usage (from repo root):
    # baseline (rerank off)
    python -m evaluation.retrieval_benchmark
    # with reranker enabled
    HEXA_RERANK_ENABLED=true python -m evaluation.retrieval_benchmark
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Load backend/.env into os.environ WITHOUT chdir so relative paths stay
# repo-root-relative and pydantic env_file lookups resolve to a missing
# ".env" (falling back to the env vars we set here). Env vars override
# env_file values, so HEXA_RERANK_ENABLED=true on the command line wins.
_envpath = BACKEND / ".env"
if _envpath.is_file():
    for _line in _envpath.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

from app.config import settings  # noqa: E402
from app.db.postgres.session import acquire  # noqa: E402
from app.query_processing.pipeline import process_query  # noqa: E402
from app.search.bm25_search import build_tsquery_sql  # noqa: E402
from app.search.hybrid_orchestrator import (  # noqa: E402
    SearchCandidate,
    search_knowledge_base,
)
from app.ranking.reranker import (  # noqa: E402
    _get_reranker,
    _model_available,
    rerank_candidates,
)
from app.ranking.rrf import rank_fusion  # noqa: E402
from app.search.pgvector_search import embed_query  # noqa: E402
from evaluation.metrics.latency_benchmark import percentile_latencies  # noqa: E402

ADMIN_USER = {"role": "super_admin", "department": "general"}
MAX_RESULTS = 100

# Gold retrieval targets, sourced from the reconciled eval dataset module
# (evaluation/datasets/eval_questions.py) — the single source of truth.
# Each gold item is (id, question, verbatim gold phrase, expected doc title).
def _load_gold() -> list[tuple[int, str, str, str]]:
    from evaluation.datasets.eval_questions import load_dataset

    gold: list[tuple[int, str, str, str]] = []
    for item in load_dataset():
        phrase = item.get("gold_phrase")
        doc_title = item.get("expected_doc_title")
        if phrase and doc_title:
            gold.append((item["id"], item["question"], phrase, doc_title))
    return gold


GOLD: list[tuple[int, str, str, str]] = _load_gold()


def _hybrid_search(conn, sub_query_texts, user, tsquery_sql) -> list[SearchCandidate]:
    """Hybrid BM25 + pgvector search, parameterised by tsquery_sql so we can
    run OR (current) vs AND (pre-fix) variants.

    Delegates to the real serving path ``search_knowledge_base`` (the same
    function the API uses) with an explicit ``tsquery_sql`` override; there
    is no duplicated SQL in the benchmark. RBAC stays in the WHERE clause.
    """
    result = search_knowledge_base(
        conn, sub_query_texts, user, max_results=MAX_RESULTS, tsquery_sql=tsquery_sql
    )
    return result.candidates


def _rrf(candidates, apply_rerank, query_text):
    """Rank Fusion (+ optional rerank) -> list[RankedCandidate] in rank order."""
    chunk_lookup = {c.chunk_id: c.__dict__ for c in candidates}
    bm25_ranked = sorted(((c.chunk_id, c.bm25_score) for c in candidates),
                         key=lambda x: x[1], reverse=True)
    vector_ranked = sorted(((c.chunk_id, c.vec_score) for c in candidates),
                           key=lambda x: x[1], reverse=True)
    ranked = rank_fusion(bm25_ranked, vector_ranked, chunk_lookup)
    if apply_rerank:
        ranked = rerank_candidates(ranked, query_text)
    return ranked


def _order_ids(ranked) -> list[int]:
    return [c.chunk_id for c in ranked]


def _gold_chunk(conn, gold_sub: str) -> tuple[int | None, str | None]:
    """Locate the chunk containing the verbatim gold phrase.

    Chunks may contain OCR/structural artifacts (newlines, tabs, runs of
    spaces), so whitespace is normalized on both sides before locating — a
    single-space gold phrase should still match a chunked paragraph.
    """
    needle = " ".join(gold_sub.lower().split())
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


def _p95(xs: list[float]) -> float:
    """p95 via the shared canonical nearest-rank definition."""
    return percentile_latencies(xs, [95])[95]


def run(output_dir: str) -> dict:
    rerank_on = bool(settings.rerank_enabled)
    rerank_model_present = _model_available(settings.rerank_model_dir)

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": "retrieval_benchmark",
        "config": {
            "rerank_enabled": rerank_on,
            "rerank_model_dir": settings.rerank_model_dir,
            "rerank_model_present": rerank_model_present,
            "rerank_top_k": settings.rerank_top_k,
            "rerank_budget_ms": settings.rerank_budget_ms,
            "embedding_model": settings.embedding_model,
            "db": settings.database_url.split("@")[-1].split("/")[0],
            "max_results": MAX_RESULTS,
        },
        "queries": [],
    }

    with acquire() as conn:
        # warm the always-on embedding model (measures the warm serving path)
        _ = embed_query("warmup")
        if rerank_on and rerank_model_present:
            r = _get_reranker()  # load ONNX session + tokenizer once
            r.score("warmup", ["warmup passage"])  # pay first-run graph cost outside the timed loop

        latencies, rerank_latencies = [], []
        or_found, and_found = 0, 0

        for qid, question, gold_sub, expected_doc in GOLD:
            gold_chunk_id, gold_doc = _gold_chunk(conn, gold_sub)

            plan = process_query(question)
            sub_query_texts = [sq.expanded for sq in plan.sub_queries] or [question]
            combined = " ".join(sub_query_texts)
            or_sql = build_tsquery_sql(combined)
            and_sql = build_tsquery_sql(combined, operator=" && ")

            serv_t0 = time.perf_counter()
            cands_or = _hybrid_search(conn, sub_query_texts, ADMIN_USER, or_sql)
            ranked_or_off = _rrf(cands_or, False, question)
            if rerank_on and rerank_model_present:
                t_r = time.perf_counter()
                ranked_or_on = rerank_candidates(ranked_or_off, question)
                rerank_latencies.append((time.perf_counter() - t_r) * 1000)
            else:
                ranked_or_on = ranked_or_off
            latency_ms = (time.perf_counter() - serv_t0) * 1000
            latencies.append(latency_ms)

            # AND ablation (pre-fix operator) — NOT part of serving latency
            cands_and = _hybrid_search(conn, sub_query_texts, ADMIN_USER, and_sql)
            ranked_and_off = _rrf(cands_and, False, question)

            def rank_of(ranked, cid):
                return _order_ids(ranked).index(cid) + 1 if cid and cid in _order_ids(ranked) else 0

            or_on_ids = _order_ids(ranked_or_on)
            and_off_ids = _order_ids(ranked_and_off)
            or_rank = rank_of(ranked_or_on, gold_chunk_id)
            and_rank = rank_of(ranked_and_off, gold_chunk_id)

            in_or = bool(gold_chunk_id) and gold_chunk_id in {c.chunk_id for c in cands_or}
            in_and = bool(gold_chunk_id) and gold_chunk_id in {c.chunk_id for c in cands_and}
            or_found += int(in_or)
            and_found += int(in_and)

            results["queries"].append({
                "id": qid, "question": question, "expected_doc": expected_doc,
                "gold_chunk_id": gold_chunk_id,
                "gold_found_in_chunk": gold_chunk_id is not None,
                "gold_chunk_doc": gold_doc,
                "gold_matches_expected_doc": (gold_doc == expected_doc) if gold_doc else False,
                "sub_queries": sub_query_texts,
                "or_rank": or_rank, "and_rank": and_rank,
                "and_retrieved_gold_at_all": in_and,
                "hits": {f"recall@{k}": int(in_or and or_rank <= k) for k in (1, 5, 10)},
                "rerank_latency_ms": round(rerank_latencies[-1], 2) if rerank_latencies else None,
                "latency_ms": round(latency_ms, 2),
            })

    n_total = len(GOLD)
    found = [q for q in results["queries"] if q["gold_chunk_id"] is not None]
    n_found = len(found)
    not_found = [q for q in results["queries"] if q["gold_chunk_id"] is None]

    def recall_at(k):
        return sum(1 for q in found if q["hits"][f"recall@{k}"]) / n_found if n_found else 0.0

    def mrr(ranks):
        inv = [1 / r for r in ranks if 0 < r <= 10]
        return float(np.mean(inv + [0.0] * (n_found - len(inv)))) if n_found else 0.0

    or_ranks = [q["or_rank"] for q in found]
    and_ranks = [q["and_rank"] for q in found]
    operator_misses = sum(1 for q in found if q["or_rank"] > 0 and q["and_rank"] == 0)

    summary = {
        "denominator": n_found,
        "gold_not_found_total": n_total - n_found,
        "gold_not_found_ids": [q["id"] for q in not_found],
        "rerank_enabled": rerank_on,
        "rerank_model_present": rerank_model_present,
        "recall_at_1": round(recall_at(1), 4),
        "recall_at_5": round(recall_at(5), 4),
        "recall_at_10": round(recall_at(10), 4),
        "mrr_10": round(mrr(or_ranks), 4),
        "retrieval_rate_or": round(or_found / n_found, 4) if n_found else 0.0,
        "retrieval_rate_and": round(and_found / n_found, 4) if n_found else 0.0,
        "and_operator_misses_over_findable": operator_misses,
        "mrr_or": round(mrr(or_ranks), 4),
        "mrr_and": round(mrr(and_ranks), 4),
        "mean_latency_ms": round(float(np.mean(latencies)), 2) if latencies else 0.0,
        "p95_latency_ms": round(_p95(latencies), 2),
        "mean_reranker_latency_ms": round(float(np.mean(rerank_latencies)), 2) if rerank_latencies else None,
        "p95_reranker_latency_ms": round(_p95(rerank_latencies), 2) if rerank_latencies else None,
        "reranker_budget_ok": (rerank_latencies and _p95(rerank_latencies) < settings.rerank_budget_ms),
    }
    results["summary"] = summary

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"retrieval_benchmark_{ts}.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    results["report_path"] = report_path

    s = summary
    print(f"Retrieval benchmark: {n_total} queries (findable: {n_found})  rerank={'ON' if rerank_on else 'OFF'}")
    print(f"  recall@1: {s['recall_at_1']:.0%}  recall@5: {s['recall_at_5']:.0%}  recall@10: {s['recall_at_10']:.0%}")
    print(f"  MRR@10:   {s['mrr_10']:.3f}")
    print(f"  retrieval rate  OR: {s['retrieval_rate_or']:.0%}   AND(pre-fix): {s['retrieval_rate_and']:.0%}")
    print(f"  AND operator misses over findable: {s['and_operator_misses_over_findable']}/{n_found}")
    if rerank_latencies:
        print(f"  reranker p50 {s.get('mean_reranker_latency_ms')}ms / p95 {s['p95_reranker_latency_ms']}ms  budget<200ms: {s['reranker_budget_ok']}")
    print(f"  end-to-end mean {s['mean_latency_ms']}ms  p95 {s['p95_latency_ms']}ms")
    print(f"  report: {report_path}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Hexta retrieval accuracy + reranker benchmark")
    parser.add_argument("--output-dir", default=str(ROOT / "evaluation" / "reports"))
    args = parser.parse_args()
    run(args.output_dir)


if __name__ == "__main__":
    main()
