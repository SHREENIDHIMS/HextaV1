"""Security regression tests — fail-closed RBAC, upload auth, secret guard."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


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
    # NOTE: _env_file=None keeps these deterministic — the repo's backend/.env
    # now carries real (rotated) dev secrets, so dotenv must not leak into the
    # assertions here.
    def test_default_secret_rejected_in_production(self):
        from app.config import Settings

        with pytest.raises(ValueError, match="HEXA_JWT_SECRET"):
            Settings(
                _env_file=None,
                environment="production",
                cors_origins="https://app.example.com",
            )

    def test_custom_secret_accepted_in_production(self):
        from app.config import Settings

        s = Settings(
            _env_file=None,
            environment="production",
            jwt_secret="a-strong-32-char-secret-not-default",
            cors_origins="https://app.example.com",
        )
        assert s.jwt_secret != "dev-only-secret-change-me-in-production-32chars"

    def test_wildcard_cors_rejected_in_production(self):
        from app.config import Settings

        with pytest.raises(ValueError, match="HEXA_CORS_ORIGINS"):
            Settings(
                _env_file=None,
                environment="production",
                jwt_secret="a-strong-32-char-secret-not-default",
                cors_origins="*",
            )

    def test_explicit_cors_accepted_in_production(self):
        from app.config import Settings

        s = Settings(
            _env_file=None,
            environment="production",
            jwt_secret="a-strong-32-char-secret-not-default",
            cors_origins="https://app.example.com,https://admin.example.com",
        )
        assert "https://app.example.com" in s.cors_origins


class TestLoginLockoutDictRow:
    """Login lockout counting must survive the pool's dict_row factory.

    The connection pool configures ``dict_row`` (session.py), so aggregate
    rows are dicts — accessing them by index crashed with KeyError (found
    live in the container, not by the mocked unit tests). test_redaction.py
    covers the value math; this class pins the dict_row access contract.
    """

    def test_is_locked_out_reads_dict_count(self):
        from app.api.v1.auth import _is_locked_out
        from app.config import settings

        conn = MagicMock()
        cur = MagicMock()
        cur.__enter__.return_value = cur
        cur.__exit__.return_value = False
        cur.fetchone.return_value = {"count": settings.login_max_attempts}
        conn.cursor.return_value = cur

        assert _is_locked_out(conn, "a@b.co") is True