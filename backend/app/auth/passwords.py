"""Password hashing and verification.

Uses bcrypt (memory-hard, salted) instead of bare SHA-256. The original
SHA-256 hashes from the initial seed are verified as a one-time
transition path so existing dev databases keep working; new hashes are
always bcrypt.
"""

from __future__ import annotations

import hashlib
import hmac

import bcrypt


def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Returns a `$2b$` string."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _is_bcrypt(stored: str) -> bool:
    return stored.startswith("$2b$") or stored.startswith("$2a$") or stored.startswith("$2y$")


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash (bcrypt, or legacy SHA-256).

    Comparison for the legacy path is constant-time to avoid a timing
    side channel.
    """
    if not stored_hash:
        return False
    if _is_bcrypt(stored_hash):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except ValueError:
            return False

    # Legacy dev-seed SHA-256 — constant-time comparison.
    candidate = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, stored_hash)
