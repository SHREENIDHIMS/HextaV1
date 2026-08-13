"""PII redaction for anything persisted from user queries.

Compliance rule (CLAUDE.md #8): every query is audit-logged. Those logs
are retained and reviewable, so raw user text must not persist with
structured PII intact. Redaction happens at write time only — retrieval
and ranking keep using the unredacted query, so this never degrades
"find the right information, don't generate new information".

This is deliberately regex-based (no ML/NLP — audit logging is in the
always-on API path, not the batch path). It masks structured identifiers:
emails, US phone numbers, US SSNs, and long digit runs (card/account
numbers). Free-text names are out of scope for automated masking.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN = re.compile(r"\b(\d{3})[- ](\d{2})[- ](\d{4})\b")
_PHONE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
# A bare run of >= 12 digits is treated as a card/account number.
_CARD = re.compile(r"\b\d{12,}\b")

_MASK_EMAIL = "[email redacted]"
_MASK_SSN = "[ssn redacted]"
_MASK_PHONE = "[phone redacted]"
_MASK_CARD = "[number redacted]"


def redact_text(text: str) -> str:
    """Mask structured PII in a query string. SSN/phone are masked before
    the generic long-digit run so the 9-digit sub-parts don't leak."""
    if not text:
        return text
    masked = _EMAIL.sub(_MASK_EMAIL, text)
    masked = _SSN.sub(_MASK_SSN, masked)
    masked = _PHONE.sub(_MASK_PHONE, masked)
    masked = _CARD.sub(_MASK_CARD, masked)
    return masked


def redact_query(query: str | None) -> str | None:
    """Redact a single query string (None-safe)."""
    return redact_text(query) if query is not None else None
