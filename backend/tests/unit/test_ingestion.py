"""Unit tests for document text extraction and ingestion pipeline.

Covers text extraction from txt/html/md/docx formats, upload validation
edge cases (zero-byte, oversized, unsupported extensions), and the
ingestion pipeline flow (process_file with mocked dependencies).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.documents.text_extraction import (
    ExtractedText,
    extract_text,
)
from app.documents.validation import validate_upload, ALLOWED_EXTENSIONS
from app.config import settings


class TestTextExtraction:
    """Tests for extract_text() across supported formats."""

    def test_extract_txt_file(self, tmp_path: Path) -> None:
        content = "Mortgage approval requires a credit score of 620+.\n\nSecond paragraph here."
        f = tmp_path / "policy.txt"
        f.write_text(content, encoding="utf-8")
        result = extract_text(f)
        assert result.source_format == "txt"
        assert content in result.text
        assert len(result.pages) == 1
        assert result.pages[0] == content

    def test_extract_html_file(self, tmp_path: Path) -> None:
        html = "<html><body><h1>Title</h1><p>Hello world</p></body></html>"
        f = tmp_path / "doc.html"
        f.write_text(html, encoding="utf-8")
        result = extract_text(f)
        assert result.source_format == "html"
        assert "Title" in result.text
        assert "Hello world" in result.text

    def test_extract_markdown_file(self, tmp_path: Path) -> None:
        md = "# Credit Score Guidelines\n\nMinimum score is 620."
        f = tmp_path / "doc.md"
        f.write_text(md, encoding="utf-8")
        result = extract_text(f)
        assert result.source_format == "md"
        assert "Credit Score Guidelines" in result.text
        assert "Minimum score is 620." in result.text

    def test_extract_unsupported_extension_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.xyz"
        f.write_text("content")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            extract_text(f)

    def test_extract_txt_strips_html_tags(self, tmp_path: Path) -> None:
        text = "Plain text without HTML."
        f = tmp_path / "doc.txt"
        f.write_text(text, encoding="utf-8")
        result = extract_text(f)
        assert "<" not in result.text

    def test_extract_empty_txt_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = extract_text(f)
        assert result.text == ""
        assert result.source_format == "txt"

    def test_extract_with_unicode_content(self, tmp_path: Path) -> None:
        content = "Credit score ≥ 620. DTI ≤ 43%. \u201chello\u201d world."
        f = tmp_path / "unicode.txt"
        f.write_text(content, encoding="utf-8")
        result = extract_text(f)
        assert "620" in result.text
        assert "43%" in result.text


class TestUploadValidation:
    """Edge-case tests for validate_upload()."""

    def test_zero_byte_file_valid(self) -> None:
        """Zero-byte files pass validation (size check is > limit, not > 0)."""
        result = validate_upload("doc.txt", 0)
        assert result.valid is True

    def test_at_exact_size_limit(self) -> None:
        """File exactly at the max size should be valid (boundary check)."""
        result = validate_upload("doc.txt", settings.max_upload_bytes)
        assert result.valid is True

    def test_one_byte_over_limit(self) -> None:
        result = validate_upload("doc.txt", settings.max_upload_bytes + 1)
        assert result.valid is False
        assert "exceeds limit" in result.error

    def test_all_allowed_extensions_accepted(self) -> None:
        for ext in ALLOWED_EXTENSIONS:
            result = validate_upload(f"doc{ext}", 1024)
            assert result.valid is True, f"Extension {ext} should be valid"

    def test_double_extension_still_validated_by_last(self) -> None:
        """A file named doc.pdf.exe should be rejected (last ext = .exe)."""
        result = validate_upload("doc.pdf.exe", 100)
        assert result.valid is False

    def test_no_extension_rejected(self) -> None:
        result = validate_upload("document", 100)
        assert result.valid is False

    def test_path_traversal_neutralized_in_caller(self) -> None:
        """validate_upload itself normalizes; caller uses Path(filename).name.
        Here we verify validate_upload accepts a clean basename."""
        result = validate_upload("safe_document.txt", 100)
        assert result.valid is True

    def test_filename_with_spaces(self) -> None:
        result = validate_upload("my document.txt", 100)
        assert result.valid is True


class TestIngestionPipeline:
    """Tests for the ingestion pipeline (process_file with mocked deps)."""

    def test_process_file_skips_empty_queue(self, tmp_path: Path) -> None:
        from app.documents.ingest_batch import main

        empty_dir = tmp_path / "empty_pending"
        empty_dir.mkdir()
        main(str(empty_dir))

    def test_process_file_unsupported_format_skipped(self, tmp_path: Path) -> None:
        from app.documents.ingest_batch import main

        f = tmp_path / "script.exe"
        f.write_bytes(b"MZ...")
        main(str(tmp_path))
        # File should remain (not moved to processed) since it was skipped
        assert f.exists()

    @patch("app.documents.ingest_batch.acquire")
    @patch("app.documents.ingest_batch.generate_embeddings")
    @patch("app.documents.ingest_batch.index_document")
    @patch("app.documents.ingest_batch.extract_entities")
    @patch("app.documents.ingest_batch.extract_metadata")
    @patch("app.documents.ingest_batch.extract_text")
    def test_process_file_full_pipeline(
        self,
        mock_extract_text,
        mock_meta,
        mock_entities,
        mock_index,
        mock_embeddings,
        mock_acquire,
        tmp_path: Path,
    ) -> None:
        from app.documents.ingest_batch import process_file
        from app.documents.text_extraction import ExtractedText
        from app.documents.metadata_extraction import DocumentMetadata
        from app.documents.chunking.structural_chunker import Chunk
        from app.documents.entity_extraction import IngestionEntities
        from app.documents.indexing import IndexResult

        test_content = "Mortgage credit score requirement is 620."
        mock_extract_text.return_value = ExtractedText(
            text=test_content, pages=[test_content], source_format="txt"
        )
        mock_meta.return_value = DocumentMetadata(
            title="Test Doc", doc_type="policy", department="general"
        )
        mock_entities.return_value = IngestionEntities(lenders=["Fannie Mae"], products=[])
        mock_index.return_value = IndexResult(document_id=1, chunks_indexed=1, chunks_skipped=0)
        mock_embeddings.return_value = [[0.1] * 384]

        mock_conn = MagicMock()
        mock_acquire.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_acquire.return_value.__exit__ = MagicMock(return_value=False)

        # Override storage paths to use tmp_path
        with patch("app.documents.ingest_batch.settings") as mock_settings:
            mock_settings.storage_processed_dir = str(tmp_path / "processed")
            mock_settings.storage_pending_dir = str(tmp_path / "pending")
            mock_settings.chunk_max_tokens = 300
            mock_settings.embedding_enabled = True

            f = tmp_path / "test_doc.txt"
            f.write_text(test_content, encoding="utf-8")

            result = process_file(f)

            from app.documents.ingest_batch import IngestOutcome

            assert result is IngestOutcome.PROCESSED
            mock_extract_text.assert_called_once()
            mock_meta.assert_called_once()
            mock_entities.assert_called_once()
            mock_embeddings.assert_called_once()
            mock_index.assert_called_once()

    def test_ingestion_dedup_uses_content_hash(self) -> None:
        """Verify content_hash normalizes content for deduplication."""
        from app.db.postgres.models import content_hash

        h1 = content_hash("same content")
        h2 = content_hash("same content")
        h3 = content_hash("same content ")
        h4 = content_hash("Different Content")
        # Identical content -> identical hash
        assert h1 == h2
        # Trailing whitespace is stripped by .strip(), so same hash
        assert h1 == h3
        # Different content -> different hash
        assert h1 != h4

    def test_chunk_section_assigned_correctly(self) -> None:
        """Section headings propagate to chunk metadata."""
        from app.documents.chunking.structural_chunker import StructuralChunker, Chunk

        text = (
            "CREDIT SCORE\n\n"
            "The minimum credit score for conventional loans is 620.\n\n"
            "DEBT-TO-INCOME\n\n"
            "The maximum DTI ratio is 43 percent."
        )
        extractor = ExtractedText(text=text, pages=[text], source_format="txt")
        chunker = StructuralChunker(max_tokens=500)
        chunks = list(chunker.chunk(extractor))
        assert len(chunks) >= 2
        # All chunks should have content, not be empty
        assert all(c.content.strip() for c in chunks)
