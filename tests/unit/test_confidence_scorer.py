"""Tests for the confidence scorer."""

from __future__ import annotations

import pytest

from confident_extract.confidence.scorer import compute_confidence


class TestComputeConfidence:
    def test_no_repair_is_perfect(self) -> None:
        score = compute_confidence(repair_applied=False, strategy_trace=())
        assert score.score == 1.0
        assert score.repair_penalty == 0.0
        assert score.label == "high"

    def test_minor_repair_is_high(self) -> None:
        score = compute_confidence(
            repair_applied=True,
            strategy_trace=("remove_trailing_commas",),
        )
        assert score.label == "high"
        assert score.score < 1.0
        assert score.repair_penalty > 0.0

    def test_single_quote_repair_medium_or_high(self) -> None:
        score = compute_confidence(
            repair_applied=True,
            strategy_trace=("normalize_single_quotes", "repair_unquoted_keys"),
        )
        assert score.score < 1.0
        assert score.label in {"high", "medium"}

    def test_prose_extraction_lowers_confidence(self) -> None:
        score = compute_confidence(
            repair_applied=True,
            strategy_trace=("extract_json_from_prose", "normalize_single_quotes"),
        )
        assert score.score <= 0.70

    def test_many_repairs_capped_at_low(self) -> None:
        many = (
            "extract_json_from_prose",
            "strip_json_comments",
            "fix_python_literals",
            "remove_trailing_commas",
            "close_unterminated_json",
            "normalize_single_quotes",
            "repair_unquoted_keys",
        )
        score = compute_confidence(repair_applied=True, strategy_trace=many)
        assert score.score >= 0.10
        assert score.repair_penalty <= 0.90
        assert score.label == "low"

    def test_score_is_float_in_range(self) -> None:
        for trace in [(), ("remove_trailing_commas",), ("extract_json_from_prose",)]:
            applied = len(trace) > 0
            score = compute_confidence(repair_applied=applied, strategy_trace=tuple(trace))
            assert 0.0 <= score.score <= 1.0

    def test_confidence_score_is_frozen(self) -> None:
        score = compute_confidence(repair_applied=False, strategy_trace=())
        with pytest.raises((AttributeError, TypeError)):
            score.score = 0.5  # type: ignore[misc]
