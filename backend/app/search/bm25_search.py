"""BM25 full-text search using PostgreSQL's built-in tsvector/ts_rank.

No external search engine needed — Postgres handles both BM25 scoring
and vector search in the same query.
"""

from __future__ import annotations

import re

# Strip punctuation and normalize for tsquery
_TSQUERY_CLEAN_RE = re.compile(r"[^a-zA-Z0-9\s]")


def _terms(text: str) -> list[str]:
    cleaned = _TSQUERY_CLEAN_RE.sub(" ", text.lower()).strip()
    return cleaned.split()


def build_tsquery_sql(text: str, config: str = "english", operator: str = " || ") -> str:
    """SQL fragment that builds a stemmed, prefix-matching tsquery.

    Each term is run through Postgres ``to_tsquery(config, %s)`` so the
    lexeme is stemmed ('veterans' -> 'veteran'), and a ``:*`` prefix in
    the parameter keeps prefix matching ('credit' matches 'credit scoring').

    The join ``operator`` defaults to OR (``||``, current serving behaviour)
    but can be `` && `` to reproduce the pre-fix AND semantics — used by the
    retrieval benchmark's AND-vs-OR ablation instead of a string hack.
    """
    terms = _terms(text)
    if not terms:
        return "''::tsquery"
    return operator.join([f"to_tsquery('{config}', %s)"] * len(terms))


def build_tsquery_params(text: str) -> list[str]:
    """Parameters for the fragment from build_tsquery_sql()."""
    return [f"{t}:*" for t in _terms(text)]


def build_tsquery(text: str, config: str = "english") -> str:
    """Compatibility helper returning a ready-to-execute tsquery string.

    Used by tests and callers that want a single executable value.
    """
    terms = _terms(text)
    if not terms:
        return "''::tsquery"
    return " || ".join([f"to_tsquery('{config}', '{t}:*')" for t in terms])
