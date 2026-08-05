"""Unit tests for response modules (package builder, validation, confidence)."""

from __future__ import annotations

from app.response.confidence_thresholds import route_by_confidence
from app.response.package_builder import (
    ResponsePackage,
    build_response_package,
    rrf_to_confidence,
)
from app.response.validation import validate_package
from app.ranking.rrf import RankedCandidate


class TestRrfToConfidence:
    def test_top_ranked_scores_100(self):
        assert rrf_to_confidence(2.0 / 61.0) == 100.0

    def test_half_strength_scores_50(self):
        assert rrf_to_confidence(1.0 / 61.0) == 50.0

    def test_zero_rrf_is_zero(self):
        assert rrf_to_confidence(0.0) == 0.0

    def test_never_exceeds_100(self):
        assert rrf_to_confidence(99.0) == 100.0

    def test_real_rrf_value_clears_no_answer_threshold(self):
        assert rrf_to_confidence(0.0328) >= 50.0


class TestConfidenceThresholds:
    def test_high_confidence_routes_to_answer(self):
        assert route_by_confidence(95.0) == "answer"

    def test_medium_confidence_routes_to_partial(self):
        assert route_by_confidence(80.0) == "partial"

    def test_low_confidence_routes_to_partial(self):
        assert route_by_confidence(60.0) == "partial"

    def test_no_answer(self):
        assert route_by_confidence(30.0) == "no_answer"

    def test_boundary_90(self):
        assert route_by_confidence(90.0) == "answer"

    def test_boundary_75(self):
        assert route_by_confidence(75.0) == "partial"

    def test_boundary_50(self):
        assert route_by_confidence(50.0) == "partial"

    def test_boundary_49(self):
        assert route_by_confidence(49.0) == "no_answer"


class TestPackageBuilder:
    def test_build_package_with_candidates(self):
        candidates = [
            RankedCandidate(
                chunk_id=1, content="The minimum credit score is 620.",
                document_id=1, title="Credit Requirements", section="Qualifications",
                chunk_type="paragraph", department="general",
                bm25_score=0.8, vec_score=0.9, rrf_score=0.05, combined_rank=1,
                is_approved=True, document_version=1,
            ),
            RankedCandidate(
                chunk_id=2, content="The maximum LTV is 80%.",
                document_id=2, title="LTV Guidelines", section="Ratios",
                chunk_type="paragraph", department="general",
                bm25_score=0.5, vec_score=0.6, rrf_score=0.03, combined_rank=2,
                is_approved=True, document_version=1,
            ),
        ]
        package = build_response_package(
            candidates=candidates,
            query_text="minimum credit score",
        )
        assert package.title == "Credit Requirements"
        assert len(package.excerpts) == 2
        assert "credit score" in package.excerpts[0].text.lower()
        assert package.response_id  # non-empty
        assert package.confidence > 0
        assert package.excerpts[0].source.department == "general"
        assert package.excerpts[0].source.is_approved is True

    def test_build_package_empty_candidates(self):
        package = build_response_package(
            candidates=[],
            query_text="nonexistent",
        )
        assert package.title == "No Results Found"
        assert len(package.excerpts) == 0
        assert package.confidence == 0.0

    def test_build_package_truncates_long_content(self):
        long_text = "x" * 1000
        candidates = [
            RankedCandidate(
                chunk_id=1, content=long_text,
                document_id=1, title="Doc", section=None, chunk_type="paragraph",
                department="general", bm25_score=0.9, vec_score=0.9,
                rrf_score=0.05, combined_rank=1,
                is_approved=True, document_version=1,
            ),
        ]
        package = build_response_package(
            candidates=candidates,
            query_text="test",
        )
        assert len(package.excerpts[0].text) <= 600


class TestValidation:
    def test_validate_high_confidence_passes(self):
        package = ResponsePackage(
            response_id="test",
            title="Test",
            confidence=95.0,
            routing="answer",
        )
        valid, reason = validate_package(package, user=None)
        assert valid is True
        assert reason == "OK"

    def test_validate_low_confidence_fails(self):
        package = ResponsePackage(
            response_id="test",
            title="Test",
            confidence=30.0,
            routing="no_answer",
        )
        valid, reason = validate_package(package, user=None)
        assert valid is False
        assert "below threshold" in reason

    def test_validate_admin_bypasses_rbac(self):
        from app.response.package_builder import Excerpt, Source

        excerpt = Excerpt(
            text="content",
            source=Source(
                chunk_id=1,
                document_id=1,
                title="Doc",
                section=None,
                chunk_type="paragraph",
                is_approved=True,
                document_version=1,
            ),
            confidence=90.0, bm25_score=0.9, vec_score=0.9,
        )
        package = ResponsePackage(
            response_id="test",
            title="Test",
            excerpts=[excerpt],
            confidence=90.0,
            routing="answer",
        )
        user = {"role": "super_admin", "department": "general", "allowed_departments": []}
        valid, _ = validate_package(package, user)
        assert valid is True

    def test_validate_unapproved_chunk_fails(self):
        from app.response.package_builder import Excerpt, Source

        excerpt = Excerpt(
            text="content",
            source=Source(
                chunk_id=1,
                document_id=1,
                title="Doc",
                section=None,
                chunk_type="paragraph",
                is_approved=False,
                document_version=1,
            ),
            confidence=90.0, bm25_score=0.9, vec_score=0.9,
        )
        package = ResponsePackage(
            response_id="test",
            title="Test",
            excerpts=[excerpt],
            confidence=90.0,
            routing="answer",
        )
        valid, reason = validate_package(package, user=None)
        assert valid is False
        assert "not approved" in reason
