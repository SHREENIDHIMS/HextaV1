"""Analytics endpoints for admin review."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.permissions import require_role
from app.dependencies import require_auth
from app.db.postgres.session import acquire

router = APIRouter()


@router.get("/knowledge-gaps")
async def knowledge_gaps(
    user: dict = Depends(require_auth),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    """View low-confidence / no-answer queries. Requires admin role."""
    require_role(user, "admin")

    with acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, query, intent, confidence, created_at "
                "FROM knowledge_gaps ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            gaps = [dict(row) for row in cur.fetchall()]

    return {"knowledge_gaps": gaps}


@router.get("/stats")
async def analytics_stats(
    user: dict = Depends(require_auth),
) -> dict:
    """Return aggregate query statistics for the analytics dashboard.

    Requires admin role. Returns:
    - total_queries: lifetime query count from audit log
    - avg_confidence: mean confidence score across all answered queries
    - answer_rate: fraction of queries routed as 'answer' (not no_answer)
    - daily_volume: list of {date, count} for last 30 days
    """
    require_role(user, "admin")

    with acquire() as conn:
        with conn.cursor() as cur:
            # Total queries
            cur.execute("SELECT COUNT(*) AS cnt FROM audit_log")
            total_row = cur.fetchone()
            total_queries = total_row["cnt"] if total_row else 0

            # Avg confidence and answer rate
            cur.execute(
                "SELECT AVG(confidence) AS avg_conf, "
                "COUNT(*) FILTER (WHERE outcome = 'answer') AS answered, "
                "COUNT(*) AS total "
                "FROM audit_log"
            )
            agg = cur.fetchone()
            avg_confidence = round(float(agg["avg_conf"] or 0), 1) if agg else 0.0
            answered = int(agg["answered"] or 0) if agg else 0
            total_all = int(agg["total"] or 1) if agg else 1
            answer_rate = round(answered / max(total_all, 1) * 100, 1)

            # Daily volume — last 30 days
            cur.execute(
                "SELECT DATE(created_at) AS day, COUNT(*) AS cnt "
                "FROM audit_log "
                "WHERE created_at >= NOW() - INTERVAL '30 days' "
                "GROUP BY day ORDER BY day"
            )
            daily_rows = cur.fetchall()
            daily_volume = [
                {"date": str(r["day"]), "count": int(r["cnt"])}
                for r in daily_rows
            ]

    return {
        "total_queries": total_queries,
        "avg_confidence": avg_confidence,
        "answer_rate": answer_rate,
        "daily_volume": daily_volume,
    }


@router.get("/top-sources")
async def top_sources(
    user: dict = Depends(require_auth),
    limit: int = Query(default=10, ge=1, le=500),
) -> dict:
    """Return the most-cited source documents. Requires admin role."""
    require_role(user, "admin")

    with acquire() as conn:
        with conn.cursor() as cur:
            # Join audit_log retrieved_ids (text[]) → chunks → documents.
            # Falls back gracefully if the join returns nothing (empty DB).
            cur.execute(
                """
                SELECT d.title, COUNT(*) AS citation_count
                FROM audit_log al
                CROSS JOIN UNNEST(al.retrieved_ids) AS cid
                JOIN document_chunks dc ON dc.id = cid
                JOIN documents d ON d.id = dc.document_id
                WHERE d.is_active = true
                GROUP BY d.title
                ORDER BY citation_count DESC
                LIMIT %s
                """,
                (limit,),
            )
            sources = [
                {"title": row["title"], "citations": int(row["citation_count"])}
                for row in cur.fetchall()
            ]

    return {"top_sources": sources}
