"""Hybrid search orchestrator.

Combines BM25 (full-text) and pgvector (semantic) search into a single
PostgreSQL query. RBAC and active-version filtering are in the WHERE
clause (CLAUDE.md rule #1).

This uses the single-query pattern — vector and BM25 in the same SQL
statement, not separate round-trips to separate services.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Sequence

from psycopg import Connection

from app.search.bm25_search import build_tsquery_params, build_tsquery_sql
from app.search.metadata_filters import get_search_filter
from app.search.pgvector_search import embed_query

logger = logging.getLogger(__name__)


@dataclass
class SearchCandidate:
    chunk_id: int
    document_id: int
    title: str
    doc_type: str
    department: str
    section: str | None
    chunk_type: str
    content: str
    is_approved: bool
    document_version: int
    bm25_score: float
    vec_score: float


@dataclass
class SearchResult:
    candidates: list[SearchCandidate] = field(default_factory=list)
    query_embedding: list[float] = field(default_factory=list)
    sub_query: str = ""


def search_knowledge_base(
    conn: Connection,
    sub_queries: Sequence[str],
    user: dict | None,
    bm25_limit: int = 25,
    vector_limit: int = 25,
    max_results: int = 100,
) -> SearchResult:
    """Run hybrid search for a set of sub-queries.

    Returns ranked candidates with both BM25 and vector scores.
    RBAC is applied in the WHERE clause per CLAUDE.md rule #1.
    """
    if not sub_queries:
        return SearchResult()

    primary_query = sub_queries[0]
    query_vector = embed_query(primary_query)

    combined_text = " ".join(sub_queries)
    tsquery_sql = build_tsquery_sql(combined_text)
    tsquery_params = build_tsquery_params(combined_text)

    # RBAC filter — applied in WHERE clause
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
    params.extend([query_vector, max_results])

    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    candidates = []
    for row in rows:
        candidates.append(SearchCandidate(
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
        ))

    logger.info(
        "Hybrid search: %d sub-queries, %d candidates returned",
        len(sub_queries), len(candidates),
    )

    return SearchResult(
        candidates=candidates,
        query_embedding=query_vector,
        sub_query=combined_text,
    )
