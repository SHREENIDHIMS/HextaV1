"""HTTP-only cookie transport for the JWT, plus CSRF double-submit defense.

Phase 1 mitigation for JWT-in-localStorage (XSS token theft): the token now
travels in an ``httpOnly``, ``SameSite=Strict`` cookie set on login instead
of being stored by the browser in localStorage. JS (and therefore an XSS
payload) cannot read it.

CSRF: ``SameSite=Strict`` alone is not a contract — a request tagged
SameSite=None upstream, older browsers, or a same-site subdomain can still
smuggle the cookie. We add the double-submit pattern: login sets a second,
JS-readable cookie (``hexa_csrf``) holding a random value. Mutating requests
must echo that value in the ``X-CSRF-Token`` header; a cross-site forger
cannot read the cookie to reproduce it.

Bearer header support is retained for scripts/eval/tests that authenticate
without cookies; ``require_csrf`` only enforces the check when the auth
cookie itself is present (i.e. a real browser session). A bearer-only caller
has no cookie an attacker could reuse, so there is nothing to protect.
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import HTTPException, Request, Response, status

from app.config import settings

AUTH_COOKIE_KEY = "hexa_token"
CSRF_COOKIE_KEY = "hexa_csrf"
CSRF_HEADER = "X-CSRF-Token"


def _cookie_kwargs(max_age: int | None = None) -> dict:
    """Common attributes for both cookies (httponly applied at the call site)."""
    return {
        "path": "/",
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        # Regenerate; cleared immediately on logout. Matches the JWT lifetime.
        "max_age": max_age if max_age is not None else settings.jwt_expiry_minutes * 60,
    }


def set_auth_cookies(response: Response, token: str) -> None:
    """Set the httpOnly JWT cookie and the JS-readable CSRF double-submit cookie."""
    kwargs = _cookie_kwargs()
    # Token cookie: httpOnly so an injected script cannot read it.
    response.set_cookie(
        key=AUTH_COOKIE_KEY,
        value=token,
        httponly=True,
        **kwargs,
    )
    # CSRF cookie must be JS-readable so the SPA can echo it in a header.
    csrf = secrets.token_urlsafe(32)
    response.set_cookie(
        key=CSRF_COOKIE_KEY,
        value=csrf,
        httponly=False,
        **kwargs,
    )


def clear_auth_cookies(response: Response) -> None:
    """Expire both cookies (logout / session teardown)."""
    for key in (AUTH_COOKIE_KEY, CSRF_COOKIE_KEY):
        response.delete_cookie(key=key, path="/")


def get_token_from_request(request: Request) -> Optional[str]:
    """Extract the JWT from the httpOnly cookie, falling back to the Bearer header.

    The cookie is the primary transport for browser sessions; the Bearer
    header remains supported so scripts, eval harnesses, and API tests can
    authenticate without an ambient cookie jar.
    """
    token = request.cookies.get(AUTH_COOKIE_KEY)
    if token:
        return token
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def require_csrf(request: Request) -> None:
    """FastAPI dependency enforcing the double-submit CSRF check.

    Enforced only when the request carries the auth cookie (a browser
    session). Bearer-only callers pass through untouched.
    """
    if AUTH_COOKIE_KEY not in request.cookies:
        return
    csrf_cookie = request.cookies.get(CSRF_COOKIE_KEY)
    header = request.headers.get(CSRF_HEADER)
    if not csrf_cookie or not header or not secrets.compare_digest(csrf_cookie, header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )