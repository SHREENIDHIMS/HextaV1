"""GLiNER domain entity extraction (query-time, lazy-loaded).

Restricted to six domain entity types: Lender, Product, Document,
Property, Number, Client. Does not expand into general NER.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_MODEL: Optional[object] = None

DOMAIN_ENTITY_TYPES: list[str] = [
    "Lender",
    "Product",
    "Document",
    "Property",
    "Number",
    "Client",
]


def get_gliner_model() -> Optional[object]:
    """Lazily load the GLiNER model. Returns None if not installed."""
    global _MODEL
    if _MODEL is None:
        try:
            import gliner

            _MODEL = gliner.load("gliner-multilingual-slim")
            logger.info("Loaded GLiNER model for domain entity extraction")
        except ImportError:
            logger.warning(
                "GLiNER not installed. Domain entity extraction at query time "
                "will fall back to dictionary-based extraction."
            )
            _MODEL = None
    return _MODEL


def extract_entities(text: str, entity_types: list[str] | None = None) -> list[dict]:
    """Extract domain entities from text using GLiNER.

    Falls back to an empty list if GLiNER is not installed.
    """
    model = get_gliner_model()
    if model is None:
        return []

    types = entity_types or DOMAIN_ENTITY_TYPES
    try:
        result = model.predict(text, labels=types)
        return [
            {
                "text": ent["text"],
                "label": ent["label"],
                "start": ent["start"],
                "end": ent["end"],
            }
            for ent in result.get("entities", [])
        ]
    except Exception as exc:
        logger.error("GLiNER entity extraction failed: %s", exc)
        return []