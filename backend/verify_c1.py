from app.db.postgres.session import acquire
from app.search.hybrid_orchestrator import search_knowledge_base

user = {"id": 1, "role": "super_admin", "department": "general", "allowed_departments": []}
with acquire() as conn:
    try:
        result = search_knowledge_base(conn=conn, sub_queries=["va loan credit score"], user=user)
        print("search ok, candidates:", len(result.candidates))
        if result.candidates:
            c = result.candidates[0]
            print("candidate:", c.chunk_id, c.title, round(c.bm25_score, 4), round(c.vec_score, 4))
    except Exception as e:
        print("SEARCH FAILED:", type(e).__name__, str(e)[:300])