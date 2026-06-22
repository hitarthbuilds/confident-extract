"""Confidence scoring for extraction results."""

from __future__ import annotations

from dataclasses import dataclass

# Penalty applied per strategy that mutated the input.
# Lower penalty = common / minor signal. Higher = heavy reconstruction.
_STRATEGY_PENALTIES: dict[str, float] = {
    "extract_json_from_prose": 0.20,
    "strip_json_comments": 0.05,
    "fix_python_literals": 0.08,
    "remove_trailing_commas": 0.05,
    "close_unterminated_json": 0.15,
    "normalize_single_quotes": 0.10,
    "repair_unquoted_keys": 0.10,
}

_DEFAULT_STRATEGY_PENALTY = 0.10


@dataclass(frozen=True, slots=True)
class ConfidenceScore:
    """Confidence signal for a single extraction result.

    Attributes:
        score: Normalized confidence value in [0.0, 1.0]. 1.0 means the input
            was already valid JSON requiring no repair. Lower values reflect
            the severity and number of repairs applied.
        repair_penalty: Total penalty deducted from 1.0 due to applied repairs.
        label: Human-readable tier: ``"high"`` (≥ 0.8), ``"medium"`` (≥ 0.5),
            or ``"low"`` (< 0.5).
    """

    score: float
    repair_penalty: float
    label: str


def compute_confidence(
    repair_applied: bool,
    strategy_trace: tuple[str, ...],
) -> ConfidenceScore:
    """Computes a confidence score from repair metadata.

    Args:
        repair_applied: Whether any repair strategy mutated the payload.
        strategy_trace: Names of strategies that actually fired.

    Returns:
        A ``ConfidenceScore`` reflecting the structural quality of the
        original input relative to the target schema.
    """
    if not repair_applied or not strategy_trace:
        return ConfidenceScore(score=1.0, repair_penalty=0.0, label="high")

    total_penalty = sum(
        _STRATEGY_PENALTIES.get(name, _DEFAULT_STRATEGY_PENALTY)
        for name in strategy_trace
    )
    total_penalty = min(total_penalty, 0.90)
    score = round(1.0 - total_penalty, 4)

    if score >= 0.80:
        label = "high"
    elif score >= 0.50:
        label = "medium"
    else:
        label = "low"

    return ConfidenceScore(score=score, repair_penalty=round(total_penalty, 4), label=label)
