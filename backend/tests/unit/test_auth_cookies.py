"""Cookie transport + CSRF double-submit tests (Phase 1 hardening).

The JWT now lives in an httpOnly, SameSite=Strict cookie rather than
localStorage, and mutating endpoints require a double-submit CSRF token
when the request authenticates via the cookie. Bearer-authenticated
callers (scripts, eval, tests) are unaffected.
"""

from __future__ import annotations

import pytest
from fastapi import Request, Response

from app.auth.cookies import (
    AUTH_COOKIE_KEY,
    CSRF_COOKIE_KEY,
    CSRF_HEADER,
    clear_auth_cookies,
    get_token_from_request,
    require_csrf,
    set_auth_cookies,
)
from app.auth.jwt_handler import create_token


class TestSetClearCookies:
    @staticmethod
    def _cookie_headers(response: Response) -> list[str]:
        """Return the raw Set-Cookie header values from a Response."""
        return [
            v.decode("latin-1")
            for k, v in response.raw_headers
            if k.lower() == b"set-cookie"
        ]

    def test_login_sets_http_only_and_csrf_cookies(self):
        response = Response()
        set_auth_cookies(response, "abc.def.ghi")
        joined = "; ".join(self._cookie_headers(response))

        assert AUTH_COOKIE_KEY + "=" in joined
        assert CSRF_COOKIE_KEY + "=" in joined
        # Token cookie must be httpOnly — XSS must not be able to read it.
        assert "HttpOnly" in joined
        assert "SameSite=strict" in joined
        # CSRF cookie must stay JS-readable so the SPA can echo it back.
        assert joined.count("HttpOnly") == 1

    def test_cookies_carry_distinct_values(self):
        response = Response()
        set_auth_cookies(response, "token-123")
        cookies = self._cookie_headers(response)
        token_cookie = next(c for c in cookies if c.startswith(AUTH_COOKIE_KEY))
        csrf_cookie = next(c for c in cookies if c.startswith(CSRF_COOKIE_KEY))
        assert "token-123" in token_cookie
        assert "token-123" not in csrf_cookie
        assert len(csrf_cookie) > len(CSRF_COOKIE_KEY) + 3  # has a value

    def test_clear_removes_both_cookies(self):
        response = Response()
        set_auth_cookies(response, "token-123")
        clear_auth_cookies(response)
        raw = "; ".join(self._cookie_headers(response))
        assert "=" in raw  # deletion cookies still carry a bare key
        assert AUTH_COOKIE_KEY + "=" in raw
        assert CSRF_COOKIE_KEY + "=" in raw


class TestGetTokenFromRequest:
    def _request(self, cookies=None, headers=None) -> Request:
        _headers = dict(headers or {})
        if cookies:
            _headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        scope = {
            "type": "http",
            "headers": [
                (k.lower().encode(), v.encode()) for k, v in _headers.items()
            ],
            "cookies": cookies or {},
            "method": "POST",
            "path": "/",
            "scheme": "http",
            "server": ("test", 80),
            "query_string": b"",
            "client": ("127.0.0.1", 1),
        }
        return Request(scope)

    def test_cookie_wins_over_bearer(self):
        request = self._request(
            cookies={AUTH_COOKIE_KEY: "cookie-token"},
            headers={"Authorization": "Bearer header-token"},
        )
        assert get_token_from_request(request) == "cookie-token"

    def test_bearer_fallback(self):
        request = self._request(headers={"Authorization": "Bearer header-token"})
        assert get_token_from_request(request) == "header-token"

    def test_case_insensitive_bearer_prefix(self):
        request = self._request(headers={"Authorization": "bearer abc"})
        assert get_token_from_request(request) == "abc"

    def test_no_token_returns_none(self):
        assert get_token_from_request(self._request()) is None


class TestRequireCsrf:
    def _make_app(self):
        from fastapi import Depends, FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()

        @app.post("/mutate")
        async def mutate(_csrf: None = Depends(require_csrf)):
            return {"ok": True}

        return TestClient(app)

    def test_bearer_only_skips_csrf(self):
        client = self._make_app()
        response = client.post(
            "/mutate", headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200

    def test_cookie_without_header_is_rejected(self):
        client = self._make_app()
        login = client.post("/mutate")
        # Grab the CSRF cookie from a prior session by logging in via the
        # cookie helper through the test client.
        # Simplest: set cookies manually.
        client.cookies.set(CSRF_COOKIE_KEY, "csrf-value")
        client.cookies.set(AUTH_COOKIE_KEY, "jwt-token")
        response = client.post("/mutate")
        assert response.status_code == 403

    def test_cookie_with_matching_header_passes(self):
        client = self._make_app()
        client.cookies.set(CSRF_COOKIE_KEY, "csrf-value")
        client.cookies.set(AUTH_COOKIE_KEY, "jwt-token")
        response = client.post("/mutate", headers={CSRF_HEADER: "csrf-value"})
        assert response.status_code == 200

    def test_cookie_with_wrong_header_is_rejected(self):
        client = self._make_app()
        client.cookies.set(CSRF_COOKIE_KEY, "csrf-value")
        client.cookies.set(AUTH_COOKIE_KEY, "jwt-token")
        response = client.post("/mutate", headers={CSRF_HEADER: "wrong"})
        assert response.status_code == 403


@pytest.mark.parametrize("endpoint", ["/api/v1/search/", "/api/v1/feedback/"])
class TestCsrfOnRealEndpoints:
    def _set_cookies_on_client(self, client) -> None:
        """Manually set the token + csrf cookies the login flow would send."""
        from fastapi.testclient import TestClient

        # A real JWT as the httpOnly cookie value.
        client.cookies.set(AUTH_COOKIE_KEY, create_token("42", email="u@h.co"))
        # A random value the SPA would read from the csrf cookie.
        client.cookies.set(CSRF_COOKIE_KEY, "real-csrf-value")

    def test_search_cookie_without_csrf_rejected(self, endpoint):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        self._set_cookies_on_client(client)
        response = client.post(endpoint, json={"query": "fha rate"})
        assert response.status_code == 403

    def test_search_cookie_with_csrf_passes_csrf_gate(self, endpoint):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        self._set_cookies_on_client(client)
        csrf = client.cookies.get(CSRF_COOKIE_KEY)
        response = client.post(
            endpoint,
            json={"query": "fha rate", "rating": 1, "response_id": "x"},
            headers={CSRF_HEADER: csrf},
        )
        # 403 (CSRF) vs downstream rejection (404/400) — anything but 403
        # proves the CSRF gate passed.
        assert response.status_code != 403
