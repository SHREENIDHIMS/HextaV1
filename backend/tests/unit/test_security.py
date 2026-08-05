"""Security regression tests — fail-closed RBAC, upload auth, secret guard."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestPermissionsFailClosed:
    def test_unknown_role_is_denied(self):
        from fastapi import HTTPException
        from app.auth.permissions import require_role

        user = {"role": "auditor", "department": "general"}
        with pytest.raises(HTTPException) as exc:
            require_role(user, "admin")
        assert exc.value.status_code == 403

    def test_none_user_is_denied(self):
        from fastapi import HTTPException
        from app.auth.permissions import require_role

        with pytest.raises(HTTPException) as exc:
            require_role(None, "admin")
        assert exc.value.status_code == 403

    def test_super_admin_passes_admin_requirement(self):
        from app.auth.permissions import require_role

        user = {"role": "super_admin", "department": "general"}
        # Must not raise
        require_role(user, "admin")

    def test_low_role_denied(self):
        from fastapi import HTTPException
        from app.auth.permissions import require_role

        user = {"role": "loan_officer", "department": "general"}
        with pytest.raises(HTTPException) as exc:
            require_role(user, "admin")
        assert exc.value.status_code == 403

    def test_unknown_required_role_fails_closed(self):
        from fastapi import HTTPException
        from app.auth.permissions import require_role

        user = {"role": "super_admin", "department": "general"}
        with pytest.raises(HTTPException):
            require_role(user, "ceo")  # not in hierarchy — never silently grant


class TestUploadAuth:
    def test_upload_requires_auth(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("doc.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 401

    def test_non_admin_cannot_upload(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: {
            "id": 2,
            "email": "officer@hexa.local",
            "role": "loan_officer",
            "department": "general",
            "allowed_departments": ["compliance"],
            "is_active": True,
        }
        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("doc.txt", b"hello", "text/plain")},
                headers={"Authorization": "Bearer whatever"},
            )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 403


class TestSearchAuth:
    def test_search_requires_auth(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/search/",
            json={"query": "fha rate"},
        )
        assert response.status_code == 401

    def test_search_rejects_invalid_token(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/search/",
            json={"query": "fha rate"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert response.status_code == 401


class TestConfigSecretGuard:
    def test_default_secret_rejected_in_production(self, monkeypatch):
        monkeypatch.delenv("HEXA_JWT_SECRET", raising=False)
        with pytest.raises(ValueError, match="HEXA_JWT_SECRET"):
            from app.config import Settings

            Settings(environment="production")

    def test_custom_secret_accepted_in_production(self):
        from app.config import Settings

        s = Settings(environment="production", jwt_secret="a-strong-32-char-secret-not-default")
        assert s.jwt_secret != "dev-only-secret-change-me-in-production-32chars"