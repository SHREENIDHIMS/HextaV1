"""spaCy NLP pipeline for query-time processing.

Uses spaCy with NER disabled — GLiNER owns entity extraction.
Only segmentation, POS tagging, and lemmatization are enabled.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_SPACY_MODEL: Optional[object] = None


def get_spacy_model() -> object:
    """Lazily load and cache the spaCy model with NER disabled."""
    global _SPACY_MODEL
    if _SPACY_MODEL is None:
        try:
            import spacy

            _SPACY_MODEL = spacy.load("en_core_web_sm", disable=["ner"])
            logger.info("Loaded spaCy model en_core_web_sm (NER disabled)")
        except OSError:
            logger.warning(
                "spaCy model en_core_web_sm not found. "
                "Install with: python -m spacy download en_core_web_sm"
            )
            _SPACY_MODEL = None
    return _SPACY_MODEL


def segment_text(text: str) -> list[str]:
    """Split text into sentences using spaCy."""
    model = get_spacy_model()
    if model is None:
        return text.split()
    doc = model(text)
    return [sent.text for sent in doc.sents]


def extract_pos(text: str) -> list[tuple[str, str]]:
    """Extract part-of-speech tags for each token."""
    model = get_spacy_model()
    if model is None:
        return []
    doc = model(text)
    return [(token.text, token.pos_) for token in doc]