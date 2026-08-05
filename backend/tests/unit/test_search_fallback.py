"""Regression tests for:
- Search returning a graceful 200 "no_answer" instead of a 500 when the
  knowledge base has no relevant chunks (low confidence is a routing
  outcome, not a server error).
- Audit logging writing sub_queries as valid JSONB (psycopg3 list
  adaptation was producing invalid JSON).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class FakeCandidate:
    def __init__(self, chunk_id: int, bm25_score: float, vec_score: float):
        self.chunk_id = chunk_id
        self.bm25_score = bm25_score
        self.vec_score = vec_score


class FakeSearchResult:
    def __init__(self, candidates):
        self.candidates = candidates


def _empty_search_result():
    return FakeSearchResult([])


def _auth_header() -> dict:
    from app.auth.jwt_handler import create_token

    return {"Authorization": f"Bearer {create_token('tester')}"}


def _fake_user() -> dict:
    return {
        "id": 1,
        "email": "admin@hexa.local",
        "full_name": "Admin User",
        "role": "super_admin",
        "department": "general",
        "allowed_departments": [],
        "is_active": True,
    }


class TestNoAnswerFallback:
    """Low-confidence / empty-KB searches return 200 no_answer, not 500."""

    def test_empty_kb_returns_no_answer_200(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _fake_user()
        try:
            with patch("app.api.v1.search.search_knowledge_base", return_value=_empty_search_result()), \
                 patch("app.api.v1.search.log_query"):
                client = TestClient(app)
                response = client.post(
                    "/api/v1/search/",
                    json={"query": "what is the fha rate"},
                    headers=_auth_header(),
                )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200
        body = response.json()
        assert body["routing"] == "no_answer"
        assert body["excerpts"] == []

    def test_no_answer_logs_validation_outcome(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _fake_user()
        try:
            with patch("app.api.v1.search.search_knowledge_base", return_value=_empty_search_result()) as mock_search, \
                 patch("app.api.v1.search.log_query") as mock_log:
                client = TestClient(app)
                response = client.post(
                    "/api/v1/search/",
                    json={"query": "fha rate"},
                    headers=_auth_header(),
                )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200
        logged = mock_log.call_args.args[0]
        assert logged.outcome.startswith("validation_failed")
        assert "Confidence" in logged.outcome


class TestRelatedQuestionsExtractive:
    """related_questions must be derived from retrieved source headings —
    never hardcoded or generated text."""

    def _package(self, excerpts):
        from app.response.package_builder import ResponsePackage

        return ResponsePackage(
            response_id="r1",
            title="T",
            excerpts=excerpts,
            confidence=90.0,
            routing="answer",
            related_questions=[],
        )

    def _excerpt(self, section):
        from app.response.package_builder import Excerpt, Source

        return Excerpt(
            text="excerpt text",
            source=Source(
                chunk_id=1,
                document_id=1,
                title="VA Loan Handbook",
                section=section,
                chunk_type="paragraph",
            ),
            confidence=95.0,
            bm25_score=10.0,
            vec_score=9.0,
        )

    def test_sections_from_evidence(self):
        from app.api.v1.search import _related_from_sources

        pkg = self._package([
            self._excerpt("Credit Requirements"),
            self._excerpt("Eligibility"),
            self._excerpt("Credit Requirements"),
            self._excerpt("Funding Fee"),
        ])
        related = _related_from_sources(pkg)
        assert related == ["Credit Requirements", "Eligibility", "Funding Fee"]
        assert all(isinstance(q, str) and q for q in related)

    def test_no_sections_yields_empty(self):
        from app.api.v1.search import _related_from_sources

        pkg = self._package([self._excerpt("")])
        assert _related_from_sources(pkg) == []

    def test_empty_excerpts_yields_empty(self):
        from app.api.v1.search import _related_from_sources

        assert _related_from_sources(self._package([])) == []

    def test_no_hardcoded_questions_in_endpoint_source(self):
        import inspect
        from app.api.v1.search import search

        source = inspect.getsource(search)
        assert "minimum credit score" not in source
        assert "What documents are required" not in source


class TestAuditLoggerJson:
    """sub_queries must be adapted as JSONB, retrieved_ids as bigint[]."""

    def test_log_query_uses_jsonb_for_sub_queries(self):
        from app.audit.audit_logger import AuditLogEntry, log_query

        entry = AuditLogEntry(
            user_id=1,
            query="va loan credit score",
            sub_queries=["va loan credit score"],
            retrieved_ids=[10, 11],
            confidence=90.0,
            response_id="abc123",
            outcome="answer",
            latency_ms=12.3,
        )

        captured = {}

        class FakeCursor:
            def execute(self, sql, params):
                captured["sql"] = sql
                captured["params"] = params

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def commit(self):
                pass

        class FakeAcquire:
            def __enter__(self):
                return FakeConn()

            def __exit__(self, *exc):
                return False

        with patch("app.audit.audit_logger.acquire", return_value=FakeAcquire()):
            log_query(entry)

        params = captured["params"]
        sub_queries_param = params[2]
        assert hasattr(sub_queries_param, "dumps") or isinstance(sub_queries_param, bytes)
        assert "va loan credit score" in str(sub_queries_param)
        assert params[3] == [10, 11]

    def test_log_query_empty_lists_become_null(self):
        from app.audit.audit_logger import AuditLogEntry, log_query

        entry = AuditLogEntry(
            user_id=None,
            query="nothing",
            sub_queries=None,
            retrieved_ids=None,
            confidence=0.0,
            response_id="",
            outcome="no_sub_queries",
            latency_ms=1.0,
        )

        captured = {}

        class FakeCursor:
            def execute(self, sql, params):
                captured["params"] = params

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def commit(self):
                pass

        class FakeAcquire:
            def __enter__(self):
                return FakeConn()

            def __exit__(self, *exc):
                return False

        with patch("app.audit.audit_logger.acquire", return_value=FakeAcquire()):
            log_query(entry)

        assert captured["params"][2] is None
        assert captured["params"][3] is None
