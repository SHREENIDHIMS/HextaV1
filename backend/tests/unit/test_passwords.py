"""Unit tests for password hashing (bcrypt with SHA-256 legacy transition)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestPasswords:
    def test_hash_and_verify_roundtrip(self):
        from app.auth.passwords import hash_password, verify_password

        h = hash_password("s3cret!")
        assert h.startswith("$2b$")
        assert h != "s3cret!"
        assert verify_password("s3cret!", h) is True

    def test_hash_is_salted(self):
        from app.auth.passwords import hash_password

        assert hash_password("same") != hash_password("same")

    def test_wrong_password_rejected(self):
        from app.auth.passwords import hash_password, verify_password

        h = hash_password("right")
        assert verify_password("wrong", h) is False

    def test_legacy_sha256_hash_verified(self):
        import hashlib
        from app.auth.passwords import verify_password

        legacy = hashlib.sha256("legacypass".encode()).hexdigest()
        assert verify_password("legacypass", legacy) is True
        assert verify_password("wrong", legacy) is False

    def test_empty_or_garbage_stored_hash(self):
        from app.auth.passwords import verify_password

        assert verify_password("x", "") is False
        assert verify_password("x", "not-a-valid-hash") is False
        assert verify_password("x", None) is False

    def test_login_uses_bcrypt_verification(self):
        from app.api.v1 import auth

        import inspect
        source = inspect.getsource(auth.login)
        assert "sha256" not in source.lower()
        assert "verify_password" in source
