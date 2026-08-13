"""Token revocation — logout support for an otherwise stateless JWT setup.

JWT issuance is stateless (HS256, no session store), so "logout" is
implemented as a small Postgres blacklist keyed on the token's ``jti``
claim. Every authenticated request checks this list; a revoked token is
rejected even if it has not yet expired. Expired blacklist rows are
purged lazily on the next revoke (no background job — CLAUDE.md rule 4).

The lookups use the ``token_blacklist_jti`` index so the per-request
overhead is a single indexed probe, not a scan.
"""

from __future__ import annotations

import logging
import time

import jwt

from app.db.postgres.session import acquire

logger = logging.getLogger(__name__)


def revoke_token(token: str) -> None:
    """Blacklist a token by its ``jti`` claim.

    Idempotent: revoking an already-revoked or already-expired token is a
    no-op. Never raises — logout must not break the client flow even if
    the DB is unavailable (the token will simply live until its natural
    expiry, which is the pre-feature behavior).
    """
    payload = _decode_payload(token)
    if not payload:
        return
    jti = payload.get("jti")
    sub = payload.get("sub")
    exp = payload.get("exp")
    if not jti:
        return

    try:
        with acquire() as conn:
            with conn.cursor() as cur:
                # Lazy purge of already-expired blacklist rows.
                cur.execute(
                    "DELETE FROM token_blacklist WHERE expires_at < now()"
                )
                cur.execute(
                    "INSERT INTO token_blacklist (jti, user_id, expires_at) "
                    "VALUES (%s, %s, to_timestamp(%s)) ON CONFLICT (jti) DO NOTHING",
                    (jti, int(sub) if sub else None, exp or time.time()),
                )
            conn.commit()
    except Exception as exc:
        logger.error("Token revoke failed: %s", exc)


def is_token_revoked(payload: dict | None) -> bool:
    """Return True if the given verified JWT payload was revoked.

    Missing ``jti`` (pre-blacklist tokens) is treated as not revoked so
    that tokens issued before this feature are not force-logged-out.
    """
    jti = (payload or {}).get("jti")
    if not jti:
        return False
    try:
        with acquire() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM token_blacklist WHERE jti = %s",
                    (jti,),
                )
                return cur.fetchone() is not None
    except Exception as exc:
        logger.error("Token blacklist check failed: %s", exc)
        # Fail closed? No — audit/verify must not take down requests on a
        # transient DB error; the signature check is the primary gate.
        return False


def _decode_payload(token: str) -> dict | None:
    """Decode the payload without signature verification.

    For revocation we need the ``jti``; the token has already been
    verified by the caller or is being logged out explicitly.
    """
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return None
