"""Tests for Phase 3 ingestion hardening.

Covers: PDF table preservation (I2), empty-text quarantine (I3), word-boundary
entity matching (I4), embedding-failure fails the file (I5), Windows move
collision handling (I7), and orphan-document cleanup on full-duplicate
re-ingest (I9).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestPdfTablePreservation:
    def test_multiline_table_block_detected_on_pdf_page(self):
        """A PDF page's table spans multiple single lines; the chunker must
        group them into one block before table detection (I2)."""
        from app.documents.chunking.structural_chunker import StructuralChunker
        from app.documents.text_extraction import ExtractedText

        page = (
            "FHA PROGRAM REQUIREMENTS\n"
            "\n"
            "Loan Type  Min FICO  Max DTI\n"
            "FHA        580       43\n"
            "VA         620       41\n"
            "USDA       640       41\n"
        )
        extracted = ExtractedText(
            text=page, pages=[page], source_format="pdf"
        )
        chunks = list(StructuralChunker(max_tokens=500).chunk(extracted))
        tables = [c for c in chunks if c.chunk_type == "table"]
        assert tables, "expected at least one table chunk"
        assert "Loan Type" in tables[0].content
        assert "FHA" in tables[0].content

    def test_plain_multiline_block_emitted_as_paragraph(self):
        from app.documents.chunking.structural_chunker import StructuralChunker
        from app.documents.text_extraction import ExtractedText

        page = "Line one of a paragraph.\nLine two of the same paragraph."
        extracted = ExtractedText(
            text=page, pages=[page], source_format="pdf"
        )
        chunks = list(StructuralChunker(max_tokens=500).chunk(extracted))
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "paragraph"
        assert "Line one" in chunks[0].content and "Line two" in chunks[0].content


class TestEmptyTextQuarantine:
    def test_empty_extraction_quarantines(self, tmp_path: Path):
        from app.documents.ingest_batch import IngestOutcome, process_file
        from app.documents.text_extraction import ExtractedText

        f = tmp_path / "scanned.pdf"
        f.write_bytes(b"%PDF-1.4 scanned")

        with patch("app.documents.ingest_batch.extract_text") as mock_extract:
            mock_extract.return_value = ExtractedText(
                text="", pages=[""], source_format="pdf"
            )
            assert process_file(f) is IngestOutcome.QUARANTINED


class TestEmbeddingFailureFailsFile:
    def test_embedding_failure_after_retries_fails_file(self, tmp_path: Path):
        from app.documents.ingest_batch import (
            EMBEDDING_ATTEMPTS,
            IngestOutcome,
            process_file,
        )
        from app.documents.chunking.structural_chunker import Chunk
        from app.documents.entity_extraction import IngestionEntities
        from app.documents.indexing import IndexResult
        from app.documents.metadata_extraction import DocumentMetadata
        from app.documents.text_extraction import ExtractedText

        f = tmp_path / "doc.txt"
        f.write_text("content here", encoding="utf-8")

        with (
            patch("app.documents.ingest_batch.extract_text") as mock_extract,
            patch("app.documents.ingest_batch.extract_metadata") as mock_meta,
            patch("app.documents.ingest_batch.extract_entities") as mock_entities,
            patch("app.documents.ingest_batch.generate_embeddings") as mock_emb,
            patch("app.documents.ingest_batch.index_document") as mock_index,
            patch("app.documents.ingest_batch.settings") as mock_settings,
        ):
            mock_extract.return_value = ExtractedText(
                text="content here", pages=["content here"], source_format="txt"
            )
            mock_meta.return_value = DocumentMetadata(
                title="Doc", doc_type="policy", department="general"
            )
            mock_entities.return_value = IngestionEntities()
            mock_emb.side_effect = RuntimeError("model unavailable")
            mock_index.return_value = IndexResult(1, 1, 0)
            mock_settings.embedding_enabled = True
            mock_settings.chunk_max_tokens = 300

            outcome = process_file(f)

        assert outcome is IngestOutcome.FAILED
        assert mock_emb.call_count == EMBEDDING_ATTEMPTS
        # NULL-embedding indexing must never happen on embedding failure.
        mock_index.assert_not_called()


class TestEntityWordBoundaries:
    def test_substring_terms_do_not_false_positive(self):
        from app.documents.entity_extraction import extract_entities

        # "arm" (alias of adjustable rate mortgage) must NOT be reported for
        # "armed"/"charm", but "FHA" must be matched inside "FHA loan".
        text = "The armed forces used a charm loan. FHA loan."
        entities = extract_entities(text)
        assert "arm" not in entities.products
        assert "arm" not in entities.lenders
        assert any(x.lower() == "fha" for x in entities.lenders)

    def test_canonical_multiword_phrase_matches(self):
        from app.documents.entity_extraction import extract_entities

        entities = extract_entities("Applicants may use an adjustable rate mortgage.")
        assert any("adjustable rate mortgage" in x.lower() for x in entities.products)


class TestMoveCollision:
    def test_move_file_survives_existing_destination(self, tmp_path: Path):
        from app.documents.ingest_batch import _move_file

        src = tmp_path / "doc.txt"
        src.write_text("content", encoding="utf-8")
        target = tmp_path / "processed"
        target.mkdir()
        (target / "doc.txt").write_text("existing", encoding="utf-8")

        dest = _move_file(src, str(target))
        assert dest != target / "doc.txt"
        assert dest.exists()
        assert not src.exists()


class TestOrphanDocumentCleanup:
    def test_full_duplicate_removes_document_row(self):
        from app.documents.chunking.structural_chunker import Chunk
        from app.documents.indexing import index_document

        conn = MagicMock()
        cur = MagicMock()
        # `with conn.cursor() as cur:` must bind to THIS mock inside the block.
        cur.__enter__.return_value = cur
        cur.__exit__.return_value = False
        cur.fetchone.return_value = {"id": 7}
        cur.rowcount = 0
        conn.cursor.return_value = cur

        chunks = [Chunk(content="dup content", section=None, chunk_type="paragraph", page_number=None)]
        result = index_document(
            conn=conn,
            doc_title="Re-ingest",
            doc_type="policy",
            department="general",
            source_path="/tmp/x.pdf",
            chunks=chunks,
        )

        assert result.chunks_indexed == 0
        assert result.chunks_skipped == 1
        # The freshly inserted document row must be removed (no orphan).
        delete_call = [
            c for c in cur.execute.call_args_list
            if str(c[0][0]).startswith("DELETE FROM documents")
        ]
        assert delete_call, "expected DELETE FROM documents on full-duplicate re-ingest"
        assert delete_call[0][0][1] == (7,)
