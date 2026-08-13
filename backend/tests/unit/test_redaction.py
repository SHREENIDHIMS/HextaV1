"""Tests for audit PII redaction (S5) and login lockout helpers (A4)."""

from __future__ import annotations


class TestRedaction:
    def test_email_is_masked(self):
        from app.audit.redaction import redact_text

        out = redact_text("Email john.doe@example.com for details")
        assert "[email redacted]" in out
        assert "john.doe@example.com" not in out

    def test_ssn_is_masked(self):
        from app.audit.redaction import redact_text

        out = redact_text("Borrower SSN is 123-45-6789")
        assert "[ssn redacted]" in out
        assert "123-45-6789" not in out

    def test_phone_is_masked(self):
        from app.audit.redaction import redact_text

        out = redact_text("Call (555) 123-4567 now")
        assert "[phone redacted]" in out
        assert "(555) 123-4567" not in out

    def test_long_digit_run_is_masked(self):
        from app.audit.redaction import redact_text

        out = redact_text("Card 4111111111111111 declined")
        assert "[number redacted]" in out
        assert "4111111111111111" not in out

    def test_plain_text_untouched(self):
        from app.audit.redaction import redact_text

        text = "What is the maximum debt-to-income ratio?"
        assert redact_text(text) == text

    def test_redact_query_none_safe(self):
        from app.audit.redaction import redact_query

        assert redact_query(None) is None


class TestLockoutWindow:
    def test_failed_attempts_zero_on_empty_result(self):
        from app.api.v1.auth import _failed_attempts_in_window

        class FakeRow:
            pass

        class FakeCur:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, *args, **kwargs):
                self._result = None

            def fetchone(self):
                return None

        class FakeConn:
            def cursor(self):
                return FakeCur()

        assert _failed_attempts_in_window(FakeConn(), "nobody@example.com") == 0

    def test_failed_attempts_counts_rows(self):
        from app.api.v1.auth import _failed_attempts_in_window

        class FakeCur:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, *args, **kwargs):
                pass

            def fetchone(self):
                return {"count": 3}

        class FakeConn:
            def cursor(self):
                return FakeCur()

        assert _failed_attempts_in_window(FakeConn(), "nobody@example.com") == 3
