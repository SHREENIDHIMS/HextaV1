"""Structural chunker for document ingestion.

Splits document text into chunks that respect document structure:
- Tables are kept as single chunks (never split mid-table)
- Headings create chunk boundaries
- Paragraphs are grouped into chunks of ~200–500 tokens

This implements the chunking strategy from Final_System_Design.md §6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

from app.documents.text_extraction import ExtractedText


@dataclass
class Chunk:
    content: str
    section: str | None
    chunk_type: str
    page_number: int | None


@dataclass
class StructuralChunker:
    max_tokens: int = 300

    def chunk(self, extracted: ExtractedText) -> Iterator[Chunk]:
        """Chunk the extracted text, respecting structure."""
        if extracted.source_format == "pdf":
            yield from self._chunk_pdf(extracted)
        else:
            yield from self._chunk_plain(extracted)

    def _chunk_pdf(self, extracted: ExtractedText) -> Iterator[Chunk]:
        """Chunk PDF pages, attempting table detection per page."""
        for page_idx, page_text in enumerate(extracted.pages):
            if not page_text.strip():
                continue
            page_num = page_idx + 1
            sections = self._split_sections(page_text)
            for section_title, body in sections:
                yield from self._chunk_section(body, section_title, page_num)

    def _split_sections(self, text: str) -> list[tuple[str | None, str]]:
        """Split text into (section_title, body) pairs based on heading patterns."""
        lines = text.split("\n")
        sections: list[tuple[str | None, str]] = []
        current_title: str | None = None
        current_body: list[str] = []

        for line in lines:
            stripped = line.strip()
            if self._is_heading(stripped):
                if current_body:
                    sections.append(
                        (current_title, "\n".join(current_body).strip())
                    )
                current_title = stripped
                current_body = []
            else:
                current_body.append(line)

        if current_body:
            sections.append(
                (current_title, "\n".join(current_body).strip())
            )

        return [(title, body) for title, body in sections if body.strip()]

    def _is_heading(self, line: str) -> bool:
        """Detect heading lines.

        The ``isupper()`` form excludes digit-bearing lines: all-caps table
        rows like ``FHA  580  43`` would otherwise be misread as headings and
        the table destroyed before it can be preserved (I2). Strong signals
        (trailing colon/em-dash, ``§``/``Section``) still match regardless.
        """
        if len(line) <= 80 and len(line.split()) <= 12:
            if line.endswith(":") or line.endswith("—"):
                return True
            if line.startswith("§") or line.startswith("Section"):
                return True
            if line.isupper() and not re.search(r"[0-9]", line):
                return True
        return False

    def _chunk_section(
        self, body: str, section: str | None, page_num: int | None
    ) -> Iterator[Chunk]:
        """Split a section body into chunks, preserving tables.

        PDF pages yield one *line* per extracted text row (pdfplumber), so
        table detection on single lines never fires — a table must be tested
        as a multi-line *block*. We therefore group consecutive non-blank
        lines into blocks first, then run table detection on each block (I2).
        """
        blocks: list[str] = []
        current: list[str] = []
        for line in body.split("\n"):
            if line.strip():
                current.append(line.strip())
            elif current:
                blocks.append("\n".join(current))
                current = []
        if current:
            blocks.append("\n".join(current))

        for block in blocks:
            if self._is_table_block(block):
                yield Chunk(
                    content=block,
                    section=section,
                    chunk_type="table",
                    page_number=page_num,
                )
                continue

            if self._count_tokens(block) <= self.max_tokens:
                yield Chunk(
                    content=block,
                    section=section,
                    chunk_type="paragraph",
                    page_number=page_num,
                )
                continue

            yield from self._split_long_text(
                block, section, page_num
            )

    def _split_long_text(
        self, text: str, section: str | None, page_num: int | None
    ) -> Iterator[Chunk]:
        """Split an over-long paragraph block on sentence boundaries."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        current: list[str] = []
        for sent in sentences:
            current.append(sent)
            if self._count_tokens("\n".join(current)) >= self.max_tokens:
                yield Chunk(
                    content="\n".join(current),
                    section=section,
                    chunk_type="paragraph",
                    page_number=page_num,
                )
                current = []
        if current:
            yield Chunk(
                content="\n".join(current),
                section=section,
                chunk_type="paragraph",
                page_number=page_num,
            )

    def _chunk_plain(self, extracted: ExtractedText) -> Iterator[Chunk]:
        """Chunk plain text content (txt, md, docx, html).

        Splits on blank lines into logical blocks. Within each block,
        detects tables and splits overly long blocks into sub-chunks.
        """
        text = extracted.text.strip()
        if not text:
            return

        blocks = re.split(r"\n\s*\n", text)

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            if self._is_table_block(block):
                yield Chunk(
                    content=block,
                    section=None,
                    chunk_type="table",
                    page_number=None,
                )
            else:
                yield from self._chunk_text_block(block)

    def _chunk_text_block(self, block: str) -> Iterator[Chunk]:
        """Split a text block into chunks of reasonable size."""
        if self._count_tokens(block) <= self.max_tokens:
            yield Chunk(
                content=block,
                section=None,
                chunk_type="paragraph",
                page_number=None,
            )
            return

        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', block)
        current: list[str] = []

        for sent in sentences:
            current.append(sent)
            if self._count_tokens("\n".join(current)) >= self.max_tokens:
                yield Chunk(
                    content="\n".join(current),
                    section=None,
                    chunk_type="paragraph",
                    page_number=None,
                )
                current = []

        if current:
            yield Chunk(
                content="\n".join(current),
                section=None,
                chunk_type="paragraph",
                page_number=None,
            )

    def _is_table_block(self, text: str) -> bool:
        """Detect table-like text blocks.

        Two signals are recognized:
        1. Pipe-delimited rows (rendered by text_extraction from pdfplumber's
           structured table extraction) — deterministic.
        2. A whitespace-column heuristic for plain-text tables: most lines
           share the same cell count, that count is >= 3, and at least two
           lines agree. The strict "share the first line's count" check used
           to miss real tables whose header row has multi-word cells (I2).
        """
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        if len(lines) < 2:
            return False

        if all("|" in line for line in lines):
            return True

        from collections import Counter

        counts = Counter(len(line.split()) for line in lines)
        (shared_count, occurrences) = counts.most_common(1)[0]
        if shared_count < 3 or occurrences < 2:
            return False
        # Paragraph lines drift in word count line-to-line; table rows don't.
        if occurrences < len(lines) * 0.6:
            return False
        return True

    def _count_tokens(self, text: str) -> int:
        """Approximate token count (words * 1.3)."""
        return int(len(text.split()) * 1.3)
