"""Recursive chunker — splits large blocks by sentence boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

from app.documents.text_extraction import ExtractedText


@dataclass
class RecursiveChunker:
    """Recursively splits large text blocks into smaller chunks."""

    max_tokens: int = 300

    def chunk(self, extracted: ExtractedText) -> Iterator[str]:
        """Yield chunks from the extracted text."""
        if extracted.source_format == "pdf":
            for page_text in extracted.pages:
                yield from self._chunk_text(page_text)
        else:
            yield from self._chunk_text(extracted.text)

    def _chunk_text(self, text: str) -> Iterator[str]:
        if self._count_tokens(text) <= self.max_tokens:
            yield text
            return

        sentences = re.split(r'(?<=[.!?])\s+', text)
        current: list[str] = []

        for sent in sentences:
            current.append(sent)
            if self._count_tokens(" ".join(current)) >= self.max_tokens:
                yield " ".join(current)
                current = []

        if current:
            yield " ".join(current)

    def _count_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.3)