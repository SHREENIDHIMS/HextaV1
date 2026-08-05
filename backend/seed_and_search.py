import time
from app.db.postgres.session import acquire
from app.search.hybrid_orchestrator import search_knowledge_base

with acquire() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM documents WHERE title='VA Loan Handbook'")
        row = cur.fetchone()
        if row is None:
            cur.execute("""
                INSERT INTO documents (title, doc_type, department, version, is_active, is_approved)
                VALUES ('VA Loan Handbook', 'sop', 'general', 1, true, true)
                RETURNING id
            """)
            doc_id = row["id"] if False else cur.fetchone()["id"]
        else:
            doc_id = row["id"]
        content = ("The minimum credit score for a VA loan is 620. Veterans Affairs home loans "
                   "require a valid Certificate of Eligibility. No down payment is required for "
                   "qualified veterans.")
        cur.execute("""
            INSERT INTO document_chunks
            (document_id, content, content_hash, department, chunk_type, section,
             is_active, is_approved, embedding)
            VALUES (%s, %s, %s, 'general', 'paragraph', 'Credit Requirements',
                    true, true, array_fill(0.1::real, ARRAY[384])::vector)
            ON CONFLICT DO NOTHING
        """, (doc_id, content, "hash-va-handbook-001"))
        conn.commit()
print("seeded")

user = {"id": 1, "role": "super_admin", "department": "general", "allowed_departments": []}
with acquire() as conn:
    result = search_knowledge_base(conn=conn, sub_queries=["va loan credit score"], user=user)
    print("candidates:", len(result.candidates))
    if result.candidates:
        c = result.candidates[0]
        print("candidate:", c.chunk_id, c.title, round(c.bm25_score, 4), round(c.vec_score, 4))