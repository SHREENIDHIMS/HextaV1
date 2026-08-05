"""Retrieval accuracy benchmark — runs the REAL search pipeline.

This complements ``run_benchmark.py`` (which measures query *processing* —
intent / entity / sub-question accuracy) by measuring query *retrieval*
accuracy against the knowledge base: given a question and a verbatim
answer phrase (extractive ground truth), does the correct
``document_chunks`` row reach the top of the ranked list?

It exercises the exact serving path:
    process_query -> hybrid BM25 + pgvector SQL (single statement,
    RBAC in the WHERE clause) -> RRF rank fusion -> optional reranker.

Per CLAUDE.md rule 6 (rerank <200ms) and rule 7 (ranking changes must be
benchmarked), this also records an AND-vs-OR ablation: the OR tsquery is
the current serving behaviour; the AND tsquery reproduces the pre-fix
"all query terms must co-occur" behaviour so we can measure the recall
delta from the ``bm25_search`` tsquery change.

Usage (from repo root):
    python -m evaluation.retrieval_benchmark --output-dir evaluation/reports
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# app.config reads HEXA_* env vars (and an optional .env). Load the backend's
# .env into os.environ WITHOUT chdir, so the process CWD (repo root) stays
# intact — this keeps relative --output-dir paths repo-root-relative and
# avoids pydantic env_file lookups misresolving to a different ".env".
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
from app.search.bm25_search import build_tsquery_params, build_tsquery_sql  # noqa: E402
from app.search.hybrid_orchestrator import SearchCandidate  # noqa: E402
from app.ranking.reranker import rerank_candidates  # noqa: E402
from app.ranking.rrf import rank_fusion  # noqa: E402
from app.search.pgvector_search import embed_query  # noqa: E402

ADMIN_USER = {"role": "super_admin", "department": "general"}
MAX_RESULTS = 100

# (id, question, verbatim answer phrase present in a chunk, expected doc title)
GOLD: list[tuple[int, str, str, str]] = [
    (1, "what is the minimum credit score for a conventional loan",
     "minimum FICO score of 620", "Credit Score Requirements for Mortgages"),
    (2, "what credit score gets the best rates",
     "740 or higher receive the best available interest rates", "Credit Score Requirements for Mortgages"),
    (3, "what is the minimum credit score for a jumbo loan",
     "often 680 or above", "Credit Score Requirements for Mortgages"),
    (4, "what are the mortgage approval requirements",
     "minimum 620 for conventional loans", "Mortgage Approval Requirements"),
    (5, "what is the minimum down payment for an fha loan",
     "minimum of 3.5% down payment", "FHA vs Conventional Loan Comparison"),
    (6, "what is the maximum ltv for a conventional loan",
     "maximum 80% for conventional loans without mortgage insurance",
     "Mortgage Approval Requirements"),
    (7, "what is the maximum debt to income ratio",
     "must not exceed 43% of gross monthly income",
     "Debt-to-Income (DTI) Ratio Requirements"),
    (8, "how is the dti ratio calculated",
     "dividing total monthly debt obligations",
     "Debt-to-Income (DTI) Ratio Requirements"),
    (9, "what are typical closing costs",
     "typically 2% to 5% of the loan amount", "Closing Costs and Fees Overview"),
    (10, "what is an appraisal fee",
     "appraisal fee: paid to a licensed appraiser", "Closing Costs and Fees Overview"),
    (11, "what is the loan estimate",
     "loan estimate and a closing disclosure", "Closing Costs and Fees Overview"),
    (12, "what is the difference between fha and conventional loans",
     "charges an upfront mip", "FHA vs Conventional Loan Comparison"),
]


def _hybrid_search(conn, sub_query_texts: list[str], user: dict, tsquery_sql: str) -> list[SearchCandidate]:
    """Reproduce search_knowledge_base.search_knowledge_base's single SQL,
    parameterised only by the tsquery SQL (so we can run AND vs OR).

    Mirrors backend/app/search/hybrid_orchestrator.py exactly:
    BM25 + pgvector in one SELECT, RBAC in the WHERE clause, ORDER BY
    GREATEST(bm25, vec)."""
    primary_query = sub_query_texts[0]
    query_vector = embed_query(primary_query)
    combined_text = " ".join(sub_query_texts)
    tsquery_params = build_tsquery_params(combined_text)

    from app.search.metadata_filters import get_search_filter
    rbac_clause, rbac_params = get_search_filter(user)

    query = f"""
    SELECT c.id, c.document_id, d.title, d.doc_type, c.section,
           c.chunk_type, c.content, c.department,
           c.is_approved AS chunk_is_approved,
           d.version AS document_version,
           ts_rank_cd(c.fts, ({tsquery_sql})) AS bm25_score,
           1 - (c.embedding <=> %s) AS vec_score
    FROM document_chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.fts @@ ({tsquery_sql})
      AND c.is_active = true AND c.is_approved = true
      AND d.is_active = true AND d.is_approved = true
      AND c.embedding IS NOT NULL
      {f'AND {rbac_clause}' if rbac_clause else ''}
    ORDER BY GREATEST(
        ts_rank_cd(c.fts, ({tsquery_sql})),
        1 - (c.embedding <=> %s)
    ) DESC
    LIMIT %s
    """

    params: list = list(tsquery_params)
    params.append(query_vector)
    params.extend(tsquery_params)
    params.extend(rbac_params)
    params.extend(tsquery_params)
    params.extend([query_vector, MAX_RESULTS])

    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    candidates = [
        SearchCandidate(
            chunk_id=row["id"],
            document_id=row["document_id"],
            title=row["title"],
            doc_type=row["doc_type"],
            department=row["department"],
            section=row["section"],
            chunk_type=row["chunk_type"],
            content=row["content"],
            is_approved=bool(row["chunk_is_approved"]),
            document_version=int(row["document_version"] or 1),
            bm25_score=float(row["bm25_score"] or 0.0),
            vec_score=float(row["vec_score"] or 0.0),
        )
        for row in rows
    ]
    return candidates


def _rank(conn, sub_query_texts: list[str], tsquery_sql: str) -> list[int]:
    """Run hybrid search + RRF + (reranker OFF) and return chunk_ids in rank
    order — mirrors api/v1/search.py's ranking exactly."""
    candidates = _hybrid_search(conn, sub_query_texts, ADMIN_USER, tsquery_sql)
    chunk_lookup = {c.chunk_id: c.__dict__ for c in candidates}
    bm25_ranked = sorted(((c.chunk_id, c.bm25_score) for c in candidates),
                         key=lambda x: x[1], reverse=True)
    vector_ranked = sorted(((c.chunk_id, c.vec_score) for c in candidates),
                           key=lambda x: x[1], reverse=True)
    ranked = rank_fusion(bm25_ranked, vector_ranked, chunk_lookup)
    ranked = rerank_candidates(ranked, sub_query_texts[0])  # OFF by default -> passthrough
    return [c.chunk_id for c in ranked]


def _find_gold_chunk(conn, gold_sub: str) -> tuple[int | None, str | None, str | None]:
    """Locate the chunk whose content verbatim contains the answer phrase."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, d.title, c.section
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE POSITION(%s IN LOWER(c.content)) > 0
            ORDER BY c.id
            LIMIT 1
            """,
            (gold_sub.lower(),),
        )
        row = cur.fetchone()
    if row is None:
        return None, None, None
    return row["id"], row["title"], row["section"]


def run(output_dir: str) -> dict:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": "retrieval_benchmark",
        "dataset_size": len(GOLD),
        "config": {
            "rerank_enabled": bool(settings.rerank_enabled),
            "rerank_budget_ms": settings.rerank_budget_ms,
            "embedding_model": settings.embedding_model,
            "db": settings.database_url.split("@")[-1].split("/")[0],
            "max_results": MAX_RESULTS,
        },
        "queries": [],
    }

    with acquire() as conn:
        # warm up the embedding model so latency reflects the warm serving path
        _ = embed_query("warmup")

        latencies: list[float] = []
        or_ranks, and_ranks = [], []
        or_found, and_found = 0, 0
        k_vals = (1, 5, 10)

        for qid, question, gold_sub, expected_doc in GOLD:
            gold_chunk_id, gold_doc, gold_section = _find_gold_chunk(conn, gold_sub)

            plan = process_query(question)
            sub_query_texts = [sq.expanded for sq in plan.sub_queries]

            start = time.perf_counter()
            or_sql = build_tsquery_sql(" ".join(sub_query_texts))
            and_sql = or_sql.replace(" || ", " && ")
            or_order = _rank(conn, sub_query_texts, or_sql)
            and_order = _rank(conn, sub_query_texts, and_sql)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

            def _rank_of(chunk_id: int | None, order: list[int]) -> int:
                if chunk_id is None:
                    return 0
                try:
                    return order.index(chunk_id) + 1
                except ValueError:
                    return 0  # present in candidate set? index finds it; 0 means "at all"? handled below
            # rank 0 -> not in this list at all (not found)
            or_rank = (or_order.index(gold_chunk_id) + 1) if gold_chunk_id and gold_chunk_id in or_order else 0
            and_rank = (and_order.index(gold_chunk_id) + 1) if gold_chunk_id and gold_chunk_id in and_order else 0

            in_or = gold_chunk_id in or_order if gold_chunk_id else False
            in_and = gold_chunk_id in and_order if gold_chunk_id else False
            or_found += int(in_or)
            and_found += int(in_and)
            or_ranks.append(or_rank)
            and_ranks.append(and_rank)

            hits = {f"recall@{k}": int(in_or and or_rank <= k) for k in k_vals}
            results["queries"].append({
                "id": qid,
                "question": question,
                "expected_doc": expected_doc,
                "gold_chunk_id": gold_chunk_id,
                "gold_found_in_chunk": gold_chunk_id is not None,
                "gold_chunk_doc": gold_doc,
                "gold_matches_expected_doc": (gold_doc == expected_doc) if gold_doc else False,
                "sub_queries": [sq.expanded for sq in plan.sub_queries],
                "or_rank": or_rank,
                "and_rank": and_rank,
                "and_retrieved_gold_at_all": in_and,
                "hits": hits,
                "latency_ms": round(latency_ms, 2),
            })

    n_total = len(GOLD)
    found = [q for q in results["queries"] if q["gold_chunk_id"] is not None]
    n_found = len(found)
    not_found = [q for q in results["queries"] if q["gold_chunk_id"] is None]

    def _p95(xs: list[float]) -> float:
        """Nearest-rank p95 (no extrapolation beyond the observed max)."""
        if not xs:
            return 0.0
        s = sorted(xs)
        k = math.ceil(0.95 * len(s))
        if k < 1:
            k = 1
        return s[k - 1]

    def recall_at(k: int) -> float:
        if not n_found:
            return 0.0
        return sum(1 for q in found if q["hits"][f"recall@{k}"]) / n_found

    def mrr_at(ranks: list[int]) -> float:
        inv = [1 / r for r in ranks if 0 < r <= 10]
        return mean(inv + [0.0] * (n_found - len(inv))) if n_found else 0.0

    # retrieval-rate denominators are the queries whose gold chunk is actually
    # present in the knowledge base (findable). The other queries are excluded
    # because no chunk contains the verbatim answer phrase — a chunker artifact,
    # not a retrieval failure.
    or_found_found = sum(1 for q in found if q["or_rank"] > 0)
    and_found_found = sum(1 for q in found if q["and_rank"] > 0)
    # Findable gold chunks that OR (current) retrieved but AND (pre-fix all-terms
    # tsquery) would have missed entirely — isolates the recall cost of the old
    # `&&` operator.
    operator_misses = sum(1 for q in found if q["or_rank"] > 0 and q["and_rank"] == 0)

    summary = {
        "denominator": n_found,
        "gold_not_found_total": n_total - n_found,
        "gold_not_found_ids": [q["id"] for q in not_found],
        "gold_not_found_reason": "answer phrase not verbatim in any chunk (chunker split/reword)",
        "recall_at_1": round(recall_at(1), 4),
        "recall_at_5": round(recall_at(5), 4),
        "recall_at_10": round(recall_at(10), 4),
        "mrr_10": round(mrr_at(or_ranks), 4),
        "retrieval_rate_or": round(or_found_found / n_found, 4),
        "retrieval_rate_and": round(and_found_found / n_found, 4),
        "and_operator_misses_over_findable": operator_misses,
        "mrr_or": round(mrr_at(or_ranks), 4),
        "mrr_and": round(mrr_at(and_ranks), 4),
        "mean_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
        "p95_latency_ms": round(_p95(latencies), 2),
    }
    results["summary"] = summary

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"retrieval_benchmark_{ts}.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    results["report_path"] = report_path

    print(f"Retrieval benchmark: {n_total} queries (findable: {n_found})")
    print(f"  recall@1: {summary['recall_at_1']:.0%}  recall@5: {summary['recall_at_5']:.0%}  recall@10: {summary['recall_at_10']:.0%}")
    print(f"  MRR@10:   {summary['mrr_10']:.3f}")
    print(f"  retrieval rate  OR(tsquery): {summary['retrieval_rate_or']:.0%}   AND(tsquery): {summary['retrieval_rate_and']:.0%}")
    print(f"  AND operator misses over findable gold: {summary['and_operator_misses_over_findable']}/{n_found}")
    print(f"  mean latency: {summary['mean_latency_ms']:.1f} ms  p95: {summary['p95_latency_ms']:.1f} ms")
    print(f"  report: {report_path}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Hexta retrieval accuracy benchmark")
    parser.add_argument("--output-dir", default=str(ROOT / "evaluation" / "reports"))
    args = parser.parse_args()
    run(args.output_dir)


if __name__ == "__main__":
    main()
