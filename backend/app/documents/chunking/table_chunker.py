"""Table chunker — preserves table structure as atomic chunks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from app.documents.text_extraction import ExtractedText


@dataclass
class TableChunker:
    """Keeps table rows together as a single chunk."""

    max_rows: int = 50

    def chunk(self, extracted: ExtractedText) -> Iterator[str]:
        """Yield table blocks from the extracted text."""
        if extracted.source_format == "pdf":
            for page_text in extracted.pages:
                yield from self._chunk_page(page_text)
        else:
            yield from self._chunk_plain(extracted.text)

    def _chunk_page(self, page_text: str) -> Iterator[str]:
        lines = page_text.split("\n")
        table_lines: list[str] = []
        for line in lines:
            if self._is_table_row(line):
                table_lines.append(line)
            else:
                if table_lines:
                    yield "\n".join(table_lines)
                    table_lines = []
        if table_lines:
            yield "\n".join(table_lines)

    def _chunk_plain(self, text: str) -> Iterator[str]:
        lines = text.split("\n")
        table_lines: list[str] = []
        for line in lines:
            if self._is_table_row(line):
                table_lines.append(line)
            else:
                if table_lines:
                    yield "\n".join(table_lines)
                    table_lines = []
        if table_lines:
            yield "\n".join(table_lines)

    def _is_table_row(self, line: str) -> bool:
        cells = line.split()
        return len(cells) >= 3