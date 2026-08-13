"""Auth endpoints (JWT login, verification, logout).

Password storage: bcrypt via app/auth/passwords.py. Legacy SHA-256
hashes from the initial dev seed are still verified for a one-time
transition, but new hashes are always bcrypt.

Security behavior (Phase 2 hardening):
- ``/login`` records every attempt to ``auth_events`` and locks the
  account for ``login_lockout_minutes`` after ``login_max_attempts``
  consecutive failures in a rolling window (A4).
- ``/logout`` revokes the presented token via the jti blacklist (A3).
- ``/verify`` re-checks ``users.is_active`` so deactivated users'
  tokens stop verifying immediately (A5). ``get_current_user`` (in
  app/dependencies.py) enforces the same on every protected route.
"""

from __future__ import annotations

import logging
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.auth.jwt_handler import create_token, verify_token
from app.auth.passwords import verify_password
from app.auth.token_blacklist import is_token_revoked, revoke_token
from app.config import settings
from app.db.postgres.session import acquire

logger = logging.getLogger(__name__)

router = APIRouter()

bearer_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenVerifyResponse(BaseModel):
    valid: bool
    user_id: int | None = None
    email: str | None = None


def _record_auth_event(conn: psycopg.Connection, email: str, event: str, ip: str | None) -> None:
    """Append a row to auth_events (never raises; auth must not 500 on a log write)."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO auth_events (email, event, ip_address) VALUES (%s, %s, %s)",
                (email, event, ip),
            )
    except Exception:
        logger.exception("auth_events write failed")


def _failed_attempts_in_window(conn: psycopg.Connection, email: str) -> int:
    """Count failed logins for the email within the lockout window."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM auth_events "
            "WHERE email = %s AND event = 'failed_login' "
            "AND created_at > now() - make_interval(mins => %s)",
            (email, settings.login_lockout_minutes),
        )
        row = cur.fetchone()
        # Pool uses dict_row (session.py), so the COUNT(*) column is "count".
        return int(row["count"]) if row else 0


def _is_locked_out(conn: psycopg.Connection, email: str) -> bool:
    """True if the email has hit the failure cap inside the window."""
    return _failed_attempts_in_window(conn, email) >= settings.login_max_attempts


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, http_request: Request) -> LoginResponse:
    """Authenticate with email + password, return a JWT.

    Locked accounts (too many recent failures) are rejected with 429
    without verifying the password, which also stops timing-based
    user-enumeration probes at the lockout threshold.
    """
    client_ip = http_request.client.host if http_request.client else None
    email = request.email.strip().lower()

    with acquire() as conn:
        if _is_locked_out(conn, email):
            _record_auth_event(conn, email, "login_locked", client_ip)
            conn.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Try again later.",
            )

        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                "SELECT id, email, password_hash, role, department, "
                "allowed_departments FROM users "
                "WHERE email = %s AND is_active = true",
                (email,),
            )
            row = cur.fetchone()

        if row is None or not verify_password(request.password, row["password_hash"]):
            _record_auth_event(conn, email, "failed_login", client_ip)
            conn.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        # Success resets the failure window for the account.
        _record_auth_event(conn, email, "successful_login", client_ip)
        conn.commit()

    token = create_token(
        subject=str(row["id"]),
        role=row["role"],
        department=row["department"],
        allowed_departments=list(row["allowed_departments"] or []),
        email=row["email"],
    )

    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_expiry_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> None:
    """Revoke the presented token so it can no longer authenticate.

    Idempotent: an already-revoked, expired, or malformed token still
    yields 204 (there is nothing left to protect). The client should
    also drop the token locally.
    """
    if credentials is not None:
        revoke_token(credentials.credentials)


@router.post("/verify", response_model=TokenVerifyResponse)
async def verify(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> TokenVerifyResponse:
    """Verify a bearer JWT token's validity.

    Requires the token to be (a) well-formed and unexpired, (b) not
    revoked, and (c) still mapped to an active user. A deactivated
    account's token therefore stops verifying immediately.
    """
    if credentials is None:
        return TokenVerifyResponse(valid=False)

    payload = verify_token(credentials.credentials)
    if payload is None or is_token_revoked(payload):
        return TokenVerifyResponse(valid=False)

    sub = payload.get("sub")
    if sub is None:
        return TokenVerifyResponse(valid=False)

    with acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM users WHERE id = %s AND is_active = true",
                (int(sub),),
            )
            active = cur.fetchone() is not None

    if not active:
        return TokenVerifyResponse(valid=False)

    return TokenVerifyResponse(
        valid=True,
        user_id=int(sub),
        email=payload.get("email"),
    )
