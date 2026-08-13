"""Dictionary-based entity extraction for document ingestion.

Unlike query-time entity extraction (which must be lightweight), the
batch ingestion pipeline can afford a slightly richer dictionary pass
to tag chunks with domain entities for later faceting/filtering.

Entities are extracted using keyword and pattern matching against the
domain vocabulary — no spaCy or GLiNER, keeping memory usage flat.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.query_processing.domain_terms import DOMAIN_TERMS

# Cache: canonical/alias surface form -> compiled word-boundary regex.
# Word boundaries stop "arm" from matching inside "armed"/"charm" (I4).
_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _boundary_pattern(term: str) -> re.Pattern[str]:
    pattern = _PATTERN_CACHE.get(term)
    if pattern is None:
        # Multi-word aliases are matched as the whole phrase; the leading and
        # trailing \b ensure the phrase is a standalone token sequence.
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        _PATTERN_CACHE[term] = pattern
    return pattern


@dataclass
class IngestionEntities:
    lenders: list[str] = field(default_factory=list)
    products: list[str] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    property_types: list[str] = field(default_factory=list)
    acronyms: list[str] = field(default_factory=list)


def extract_entities(text: str) -> IngestionEntities:
    """Extract domain entities from text using dictionary matching.

    Matching is whole-word/phrase aware (word-boundary regexes), so a
    term like "arm" is not reported for "armed forces" or "charm".
    """
    entities = IngestionEntities()

    for canonical, meta in DOMAIN_TERMS.items():
        entity_type = meta.get("type", "")
        aliases = meta.get("aliases", [])
        all_terms = [canonical] + aliases
        for term in all_terms:
            if not _boundary_pattern(term).search(text):
                continue
            if entity_type in ("acronym", "abbreviation"):
                if term not in entities.acronyms:
                    entities.acronyms.append(term)
            elif entity_type == "lender" or "lender" in entity_type:
                if term not in entities.lenders:
                    entities.lenders.append(term)
            elif entity_type == "product" or "product" in entity_type:
                if term not in entities.products:
                    entities.products.append(term)
            elif entity_type == "document" or "document" in entity_type:
                if term not in entities.documents:
                    entities.documents.append(term)
            elif entity_type == "property" or "property" in entity_type:
                if term not in entities.property_types:
                    entities.property_types.append(term)

    return entities
