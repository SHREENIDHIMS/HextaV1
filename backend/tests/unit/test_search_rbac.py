"""Unit tests for RBAC enforcement in search (CLAUDE.md rule #1).

PRIMARY enforcement — RBAC and active-version filtering happen in the SQL
WHERE clause at query time — is verified here by capturing the SQL that
``search_knowledge_base`` executes. The validation safety-net (rule #1
redundant check) is also covered. These run DB-free (the cursor is mocked)
so they execute in CI via ``pytest tests/unit/``.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.response.package_builder import Excerpt, ResponsePackage, Source
from app.response.validation import validate_package
from app.search.hybrid_orchestrator import search_knowledge_base

# Columns selected by the hybrid query in hybrid_orchestrator.py
_COLS = [
    "id", "document_id", "title", "doc_type", "section", "chunk_type",
    "content", "department", "chunk_is_approved", "document_version",
    "bm25_score", "vec_score",
]

DUMMY_VEC = [0.0] * 384


def _row(**kw):
    base = dict.fromkeys(_COLS, None)
    base["chunk_is_approved"] = True
    base["document_version"] = 1
    base["bm25_score"] = 1.0
    base["vec_score"] = 0.9
    base.update(kw)
    return base


def _fake_conn(rows):
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__.return_value = cur
    cur.__exit__.return_value = False
    cur.fetchall.return_value = list(rows)
    conn.cursor.return_value = cur
    return conn, cur


class TestSearchRBACInSQL:
    """Assert the RBAC clause is injected into the hybrid SQL WHERE (rule #1
    primary enforcement), not applied as a post-hoc Python filter."""

    _PATCH = "app.search.hybrid_orchestrator.embed_query"

    def test_restricted_user_sql_contains_department_filter(self):
        conn, cur = _fake_conn([_row(id=1, document_id=1, title="T", doc_type="policy",
                                    section="s", chunk_type="paragraph", content="x",
                                    department="general")])
        user = {"role": "loan_officer", "department": "general",
                "allowed_departments": ["compliance"]}
        with patch(self._PATCH, return_value=DUMMY_VEC):
            search_knowledge_base(conn, ["credit score"], user)
        sql = cur.execute.call_args[0][0]
        assert "fts @@" in sql                      # hybrid text match still present
        assert "d.department = ANY" in sql          # RBAC pushed into WHERE
        assert "1=0" not in sql                     # not a blanket deny

    def test_admin_user_sql_omits_department_filter(self):
        conn, cur = _fake_conn([])
        user = {"role": "super_admin", "department": "general", "allowed_departments": []}
        with patch(self._PATCH, return_value=DUMMY_VEC):
            search_knowledge_base(conn, ["credit score"], user)
        sql = cur.execute.call_args[0][0]
        assert "d.department" not in sql            # admin bypasses RBAC in SQL

    def test_unauthenticated_user_denied_in_sql(self):
        conn, cur = _fake_conn([])
        with patch(self._PATCH, return_value=DUMMY_VEC):
            search_knowledge_base(conn, ["credit score"], None)
        sql = cur.execute.call_args[0][0]
        assert "1=0" in sql                         # deny-all for unauthenticated


class TestValidationSafetyNet:
    """Redundant safety-net re-check (rule #1) over the assembled package."""

    @staticmethod
    def _pkg(dept: str, approved: bool = True) -> ResponsePackage:
        src = Source(chunk_id=1, document_id=1, title="T", section=None,
                     chunk_type="paragraph", department=dept,
                     is_approved=approved, document_version=1)
        ex = Excerpt(text="x", source=src, confidence=95.0, bm25_score=1.0, vec_score=0.9)
        return ResponsePackage(response_id="r", title="T", excerpts=[ex],
                               confidence=95.0, routing="answer")

    def test_rejects_unauthorized_department(self):
        user = {"role": "loan_officer", "department": "general", "allowed_departments": ["compliance"]}
        ok, reason = validate_package(self._pkg("underwriting"), user)
        assert not ok
        assert "RBAC" in reason

    def test_rejects_unapproved_chunk(self):
        user = {"role": "loan_officer", "department": "general", "allowed_departments": ["compliance"]}
        ok, reason = validate_package(self._pkg("general", approved=False), user)
        assert not ok
        assert "not approved" in reason

    def test_allows_authorized_department(self):
        user = {"role": "loan_officer", "department": "general", "allowed_departments": ["compliance"]}
        ok, reason = validate_package(self._pkg("general"), user)
        assert ok, reason
