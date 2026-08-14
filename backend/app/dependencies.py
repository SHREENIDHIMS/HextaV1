"""FastAPI dependency injection.

Provides:
- ``get_db`` — yields a pooled Postgres connection per request
- ``get_current_user`` — extracts and verifies JWT, returns the user row
- ``require_department_access`` — RBAC scope resolver from the JWT

Authentication is enforced backend-side. The JWT travels in an httpOnly
cookie (see app/auth/cookies.py); the Bearer header is still accepted so
scripts and eval harnesses can authenticate without a cookie jar.
"""

from __future__ import annotations

from typing import Annotated, Optional

import psycopg
from fastapi import Depends, HTTPException, Request, status

from app.auth.cookies import get_token_from_request
from app.auth.jwt_handler import verify_token
from app.auth.token_blacklist import is_token_revoked
from app.db.postgres.session import acquire


def get_db() -> psycopg.Connection:
    """Yield a pooled Postgres connection for a single request."""
    with acquire() as conn:
        yield conn


async def get_current_user(request: Request) -> dict | None:
    """Extract and verify JWT from the auth cookie, then the Bearer header.

    Returns the user dict if valid, None if no token provided
    (callers can decide whether auth is required).
    """
    token = get_token_from_request(request)
    if not token:
        return None
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if is_token_revoked(payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, full_name, role, department, allowed_departments, is_active "
                "FROM users WHERE id = %s AND is_active = true",
                (user_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return dict(row)


async def require_auth(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """Dependency that requires a valid authenticated user."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
