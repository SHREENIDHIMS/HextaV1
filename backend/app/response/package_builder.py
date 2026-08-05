"""Response package builder.

Assembles retrieved chunks into the ResponsePackage shape. Every field
must trace back verbatim or near-verbatim to a source chunk — no
synthesis (CLAUDE.md doctrine).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from app.config import settings
from app.ranking.rrf import RRF_K, RankedCandidate


@dataclass
class Source:
    chunk_id: int
    document_id: int
    title: str
    section: str | None
    chunk_type: str
    department: str | None = None
    is_approved: bool = True
    document_version: int = 1
    page_number: int | None = None


@dataclass
class Excerpt:
    text: str
    source: Source
    confidence: float
    bm25_score: float
    vec_score: float


@dataclass
class ResponsePackage:
    response_id: str
    title: str
    excerpts: list[Excerpt] = field(default_factory=list)
    related_questions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    routing: str = "answer"
    max_excerpt_chars: int = 600


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


def rrf_to_confidence(rrf_score: float, k: int = RRF_K) -> float:
    """Map an RRF score to a 0–100 confidence scale.

    RRF scores are tiny (a candidate ranked #1 in both lists scores
    1/(k+1) + 1/(k+1) ≈ 0.033 with k=60), so multiplying by 100 would
    never clear the 50/75/90 confidence bands. Normalise by the
    theoretical maximum RRF score (rank 1 in both lists) so a
    top-ranked match scores 100.
    """
    max_rrf = 2.0 / (k + 1)
    if max_rrf <= 0 or rrf_score <= 0:
        return 0.0
    return min(rrf_score / max_rrf * 100.0, 100.0)


def build_response_package(
    candidates: list[RankedCandidate],
    query_text: str,
    user_departments: list[str] | None = None,
) -> ResponsePackage:
    """Build a ResponsePackage from ranked candidates.

    - Takes top-N candidates (max_evicence_docs from config)
    - Truncates excerpts to max_excerpt_chars
    - Computes confidence from top candidate's RRF score (0-100)
    - Extracts related questions from query entities
    """
    max_docs = settings.max_evidence_docs
    top = candidates[:max_docs]

    excerpts: list[Excerpt] = []
    for c in top:
        confidence = rrf_to_confidence(c.rrf_score)
        excerpts.append(Excerpt(
            text=_truncate(c.content, settings.max_excerpt_chars),
            source=Source(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                title=c.title,
                section=c.section,
                chunk_type=c.chunk_type,
                department=c.department or None,
                is_approved=c.is_approved,
                document_version=c.document_version,
            ),
            confidence=round(confidence, 1),
            bm25_score=round(c.bm25_score, 4),
            vec_score=round(c.vec_score, 4),
        ))

    # Response title from the most relevant document
    title = excerpts[0].source.title if excerpts else "No Results Found"

    # Confidence from the top candidate
    top_confidence = excerpts[0].confidence if excerpts else 0.0

    # Generate response_id for audit tracing
    response_id = hashlib.sha256(
        f"{query_text}:{top_confidence}".encode()
    ).hexdigest()[:16]

    return ResponsePackage(
        response_id=response_id,
        title=title,
        excerpts=excerpts,
        confidence=top_confidence,
        max_excerpt_chars=settings.max_excerpt_chars,
    )
