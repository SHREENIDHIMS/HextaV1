"""Checklist chunker — keeps checklist items together."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

from app.documents.text_extraction import ExtractedText


@dataclass
class ChecklistChunker:
    """Groups checklist items into single chunks."""

    def chunk(self, extracted: ExtractedText) -> Iterator[str]:
        """Yield checklist blocks from the extracted text."""
        if extracted.source_format == "pdf":
            for page_text in extracted.pages:
                yield from self._chunk_page(page_text)
        else:
            yield from self._chunk_plain(extracted.text)

    def _chunk_page(self, page_text: str) -> Iterator[str]:
        lines = page_text.split("\n")
        checklist_lines: list[str] = []
        for line in lines:
            if self._is_checklist_item(line):
                checklist_lines.append(line)
            else:
                if checklist_lines:
                    yield "\n".join(checklist_lines)
                    checklist_lines = []
        if checklist_lines:
            yield "\n".join(checklist_lines)

    def _chunk_plain(self, text: str) -> Iterator[str]:
        lines = text.split("\n")
        checklist_lines: list[str] = []
        for line in lines:
            if self._is_checklist_item(line):
                checklist_lines.append(line)
            else:
                if checklist_lines:
                    yield "\n".join(checklist_lines)
                    checklist_lines = []
        if checklist_lines:
            yield "\n".join(checklist_lines)

    def _is_checklist_item(self, line: str) -> bool:
        stripped = line.strip()
        return bool(re.match(r"^[\-\*]\s+", stripped))