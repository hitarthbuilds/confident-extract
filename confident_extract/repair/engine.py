"""Repair engine orchestration for malformed JSON-like text."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from confident_extract.repair.strategies import (
    close_unterminated_json,
    normalize_single_quotes,
    remove_trailing_commas,
    repair_unquoted_keys,
    try_orjson_parse,
)

_RepairStrategy = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class RepairResult:
    """Result returned by the repair engine.

    Attributes:
        data: Parsed JSON value when repair succeeds, otherwise `None`.
        repaired_text: Final text after all applied repair strategies.
        repair_applied: Whether any strategy mutated the input.
        repair_attempts: Number of applied strategy mutations attempted.
        strategy_trace: Names of strategies that actually mutated the input.
    """

    data: object | None
    repaired_text: str
    repair_applied: bool
    repair_attempts: int
    strategy_trace: tuple[str, ...]


_STRATEGIES: tuple[tuple[str, _RepairStrategy], ...] = (
    ("remove_trailing_commas", remove_trailing_commas),
    ("close_unterminated_json", close_unterminated_json),
    ("normalize_single_quotes", normalize_single_quotes),
    ("repair_unquoted_keys", repair_unquoted_keys),
)


def repair(text: str, max_attempts: int = 3) -> RepairResult:
    """Attempts ordered, deterministic JSON repair.

    Args:
        text: JSON-like text to parse and, if needed, repair.
        max_attempts: Maximum number of actual text mutations to attempt.

    Returns:
        A repair result containing parsed data on success or the final
        unrecoverable text and trace on failure.
    """
    parsed, success = try_orjson_parse(text)
    if success:
        return RepairResult(
            data=parsed,
            repaired_text=text,
            repair_applied=False,
            repair_attempts=0,
            strategy_trace=(),
        )

    if max_attempts <= 0:
        return RepairResult(
            data=None,
            repaired_text=text,
            repair_applied=False,
            repair_attempts=0,
            strategy_trace=(),
        )

    current_text = text
    trace: list[str] = []
    attempts = 0

    for strategy_name, strategy in _STRATEGIES:
        updated_text = strategy(current_text)
        if updated_text == current_text:
            continue

        current_text = updated_text
        trace.append(strategy_name)
        attempts += 1

        parsed, success = try_orjson_parse(current_text)
        if success:
            return RepairResult(
                data=parsed,
                repaired_text=current_text,
                repair_applied=True,
                repair_attempts=attempts,
                strategy_trace=tuple(trace),
            )

        if attempts >= max_attempts:
            break

    return RepairResult(
        data=None,
        repaired_text=current_text,
        repair_applied=attempts > 0,
        repair_attempts=attempts,
        strategy_trace=tuple(trace),
    )
