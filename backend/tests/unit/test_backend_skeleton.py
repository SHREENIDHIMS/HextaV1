"""Unit tests for the backend skeleton.

Tests:
- App starts and health check works
- Auth endpoints are wired (login fails with invalid creds)
- Search endpoint returns 501 (stub)
- JWT handler creates and verifies tokens
- RBAC resolves departments correctly
"""

from __future__ import annotations

import pytest


class TestAppStartup:
    """Verify the FastAPI app initializes correctly."""

    def test_app_creation(self):
        from app.main import app

        assert app is not None
        assert app.title == "Hexta"

    def test_health_endpoint_exists(self):
        from app.main import app

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/health" in paths

    def test_api_health_endpoint_exists(self):
        from app.main import app

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v1/health" in paths

    def test_api_docs_endpoints_exist(self):
        from app.main import app

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v1/docs" in paths
        assert "/api/v1/openapi.json" in paths

    def test_api_router_included(self):
        from app.main import app

        paths = list(app.openapi()["paths"].keys())
        assert any("/api/v1/auth" in p for p in paths)


class TestAuthEndpoints:
    """Test auth endpoint stubs and JWT handling."""

    def test_login_invalid_credentials(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.com", "password": "wrong"},
        )
        assert response.status_code == 401

    def test_login_empty_credentials(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "", "password": ""},
        )
        assert response.status_code == 401

    def test_verify_invalid_token(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False


class TestJWTHandler:
    """Test JWT token creation and verification."""

    def test_create_and_verify_token(self):
        from app.auth.jwt_handler import create_token, verify_token

        token = create_token(
            subject="1",
            role="loan_officer",
            department="general",
            allowed_departments=["general", "compliance"],
        )
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["role"] == "loan_officer"
        assert payload["department"] == "general"
        assert "general" in payload["allowed_departments"]
        assert "compliance" in payload["allowed_departments"]

    def test_verify_invalid_token(self):
        from app.auth.jwt_handler import verify_token

        assert verify_token("invalid.token.here") is None

    def test_verify_empty_token(self):
        from app.auth.jwt_handler import verify_token

        assert verify_token("") is None

    def test_verify_none_token(self):
        from app.auth.jwt_handler import verify_token

        assert verify_token(None) is None


class TestRBAC:
    """Test RBAC department resolution."""

    def test_resolve_user_departments(self):
        from app.auth.rbac import resolve_user_departments

        user = {
            "department": "general",
            "allowed_departments": ["general", "compliance"],
        }
        depts = resolve_user_departments(user)
        assert "general" in depts
        assert "compliance" in depts

    def test_resolve_user_none(self):
        from app.auth.rbac import resolve_user_departments

        assert resolve_user_departments(None) == []

    def test_is_admin_super_admin(self):
        from app.auth.rbac import is_admin

        user = {"role": "super_admin", "department": "general"}
        assert is_admin(user) is True

    def test_is_admin_loan_officer(self):
        from app.auth.rbac import is_admin

        user = {"role": "loan_officer", "department": "general"}
        assert is_admin(user) is False

    def test_get_search_filter_admin(self):
        from app.auth.rbac import get_search_filter

        user = {"role": "super_admin", "department": "general"}
        clause, params = get_search_filter(user)
        assert clause == ""
        assert params == []

    def test_get_search_filter_loan_officer(self):
        from app.auth.rbac import get_search_filter

        user = {
            "role": "loan_officer",
            "department": "general",
            "allowed_departments": ["compliance"],
        }
        clause, params = get_search_filter(user)
        assert "department" in clause
        assert "general" in params
        assert "compliance" in params


class TestEndpoints:
    """Verify implemented endpoints respond correctly."""

    def test_search_endpoint_returns_response(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/search/",
            json={"query": "mortgage rates"},
            headers={"Authorization": "Bearer test"},
        )
        # Search endpoint is fully implemented — returns JSON or auth error
        assert response.status_code in (200, 401)

    def test_search_success_path_returns_200(self):
        """The search happy path (package build → validate → audit) must return
        200 with excerpts, not just the 401 stub fallback (T4)."""
        from fastapi.testclient import TestClient
        from unittest.mock import patch

        from app.main import app
        from app.dependencies import get_current_user
        from app.search.hybrid_orchestrator import SearchCandidate, SearchResult

        def fake_user():
            return {
                "id": 1,
                "email": "admin@hexa.local",
                "full_name": "Admin User",
                "role": "super_admin",
                "department": "general",
                "allowed_departments": [],
                "is_active": True,
            }

        def fake_result(*args, **kwargs):
            cand = SearchCandidate(
                chunk_id=1,
                document_id=1,
                title="Credit Score Requirements for Mortgages",
                doc_type="policy",
                department="general",
                section="Minimum Credit Score",
                chunk_type="paragraph",
                content="The minimum credit score for a conventional loan is 620.",
                is_approved=True,
                document_version=1,
                bm25_score=0.9,
                vec_score=0.95,
            )
            return SearchResult(candidates=[cand])

        app.dependency_overrides[get_current_user] = fake_user
        try:
            with patch("app.api.v1.search.search_knowledge_base", side_effect=fake_result), \
                 patch("app.api.v1.search.log_query"):
                client = TestClient(app)
                response = client.post(
                    "/api/v1/search/",
                    json={"query": "minimum credit score"},
                    headers={"Authorization": "Bearer valid-token"},
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["routing"] == "answer"
        assert body["confidence"] > 0
        assert len(body["excerpts"]) >= 1
        assert body["excerpts"][0]["source"]["title"] == "Credit Score Requirements for Mortgages"
        assert body["response_id"]

    def test_search_rejects_empty_query(self):
        """B6: empty or over-long queries are rejected by the API schema."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: {
            "id": 1, "email": "admin@hexa.local", "full_name": "Admin",
            "role": "super_admin", "department": "general",
            "allowed_departments": [], "is_active": True,
        }
        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/search/",
                json={"query": ""},
                headers={"Authorization": "Bearer x"},
            )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 422

    def test_documents_upload_requires_auth(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post("/api/v1/documents/upload")
        # Upload endpoint requires auth before any file validation
        assert response.status_code == 401

    def test_admin_users_endpoint_requires_auth(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 401

    def test_analytics_endpoint_requires_auth(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/v1/analytics/knowledge-gaps")
        assert response.status_code == 401

    def test_documents_list_endpoint_requires_auth(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/v1/documents/")
        assert response.status_code == 401

    def test_feedback_endpoint_exists(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post("/api/v1/feedback/", json={})
        assert response.status_code == 401
