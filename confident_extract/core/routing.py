"""Confidence-based routing and fallback for the extraction pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

from confident_extract.core.extractor import extract
from confident_extract.core.result import ExtractionResult

T = TypeVar("T")

_FallbackFn = Callable[[ExtractionResult[T]], ExtractionResult[T]]


@dataclass
class RoutingConfig:
    """Configuration for confidence-based extraction routing.

    Attributes:
        min_confidence: Results with ``confidence.score`` below this threshold
            trigger the ``on_low_confidence`` callback when provided.
        on_low_confidence: Optional callback invoked when confidence is below
            ``min_confidence``. Receives the low-confidence result and must
            return a replacement ``ExtractionResult``. Use this to re-prompt
            the model, fall back to a default, or route to human review.
        raise_on_low_confidence: When ``True`` and no ``on_low_confidence``
            callback is set, raises ``LowConfidenceError`` instead of
            returning the low-confidence result.
    """

    min_confidence: float = 0.5
    on_low_confidence: _FallbackFn | None = field(default=None, repr=False)
    raise_on_low_confidence: bool = False


class LowConfidenceError(Exception):
    """Raised when extraction confidence falls below the configured threshold.

    Attributes:
        result: The low-confidence ``ExtractionResult`` that triggered the error.
    """

    def __init__(self, result: ExtractionResult) -> None:  # type: ignore[type-arg]
        """Initialises the error with the low-confidence extraction result."""
        self.result = result
        score = result.confidence.score
        label = result.confidence.label
        trace = ", ".join(result.strategy_trace) or "none"
        super().__init__(
            f"Extraction confidence {score:.2f} ({label}) is below threshold. "
            f"Strategies applied: {trace}."
        )


def extract_with_routing(
    text: str,
    schema: type[T],
    *,
    config: RoutingConfig | None = None,
) -> ExtractionResult[T]:
    """Extracts a typed instance with optional confidence-based fallback routing.

    Runs the standard :func:`~confident_extract.extract` pipeline and then
    checks the confidence score against the configured threshold. When
    confidence is too low, the result is either passed to a fallback callback,
    raised as a :exc:`LowConfidenceError`, or returned as-is.

    Args:
        text: Raw input text to extract from.
        schema: Target schema type.
        config: Routing configuration. Uses permissive defaults when omitted.

    Returns:
        An ``ExtractionResult`` — either the original or the output of the
        ``on_low_confidence`` callback.

    Raises:
        LowConfidenceError: When confidence is below threshold and
            ``config.raise_on_low_confidence`` is ``True``.

    Example::

        from confident_extract.core.routing import RoutingConfig, extract_with_routing

        def reprompt(result):
            # Call the LLM again with a stricter prompt, then re-extract
            new_text = call_llm_again(result.raw_input)
            return extract(new_text, Invoice)

        config = RoutingConfig(min_confidence=0.8, on_low_confidence=reprompt)
        result = extract_with_routing(llm_output, Invoice, config=config)
    """
    result = extract(text, schema)
    effective_config = config or RoutingConfig()

    if result.confidence.score >= effective_config.min_confidence:
        return result

    if effective_config.on_low_confidence is not None:
        return effective_config.on_low_confidence(result)

    if effective_config.raise_on_low_confidence:
        raise LowConfidenceError(result)

    return result


def filter_by_confidence(
    results: list[ExtractionResult[T]],
    *,
    min_score: float = 0.5,
    label: str | None = None,
) -> tuple[list[ExtractionResult[T]], list[ExtractionResult[T]]]:
    """Splits a list of results into (confident, uncertain) by confidence threshold.

    Args:
        results: List of ``ExtractionResult`` instances to split.
        min_score: Minimum ``confidence.score`` to be considered confident.
        label: When provided, overrides ``min_score`` — only results whose
            ``confidence.label`` equals this value are considered confident.
            Accepts ``"high"``, ``"medium"``, or ``"low"``.

    Returns:
        A tuple of ``(confident_results, uncertain_results)``.

    Example::

        confident, uncertain = filter_by_confidence(results, min_score=0.8)
        # Send uncertain to human review queue
        review_queue.extend(uncertain)
    """
    confident: list[ExtractionResult[T]] = []
    uncertain: list[ExtractionResult[T]] = []

    for result in results:
        passes = (
            result.confidence.label == label
            if label is not None
            else result.confidence.score >= min_score
        )
        if passes:
            confident.append(result)
        else:
            uncertain.append(result)

    return confident, uncertain
