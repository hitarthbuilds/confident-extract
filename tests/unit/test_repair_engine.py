"""Unit tests for repair engine orchestration."""

from __future__ import annotations

from confident_extract.repair.engine import RepairResult, repair


def test_repair_result_is_dataclass_like_and_immutable() -> None:
    """Constructs a repair result with the documented fields."""
    result = RepairResult(
        data={"invoice": 1},
        repaired_text='{"invoice": 1}',
        repair_applied=False,
        repair_attempts=0,
        strategy_trace=(),
    )

    assert result.data == {"invoice": 1}
    assert result.repaired_text == '{"invoice": 1}'
    assert result.repair_applied is False
    assert result.repair_attempts == 0
    assert result.strategy_trace == ()


def test_repair_fast_path_short_circuits_valid_json() -> None:
    """Returns immediately for already valid JSON."""
    result = repair('{"invoice": 1, "status": "paid"}')

    assert result.data == {"invoice": 1, "status": "paid"}
    assert result.repaired_text == '{"invoice": 1, "status": "paid"}'
    assert result.repair_applied is False
    assert result.repair_attempts == 0
    assert result.strategy_trace == ()


def test_repair_recovers_with_remove_trailing_commas_only() -> None:
    """Stops after the first strategy when it makes the payload valid."""
    result = repair('{"invoice": 1, "items": [1, 2,]}')

    assert result.data == {"invoice": 1, "items": [1, 2]}
    assert result.repaired_text == '{"invoice": 1, "items": [1, 2]}'
    assert result.repair_applied is True
    assert result.repair_attempts == 1
    assert result.strategy_trace == ("remove_trailing_commas",)


def test_repair_recovers_with_close_unterminated_json_only() -> None:
    """Repairs truncated container structures when earlier strategies no-op."""
    result = repair('{"invoice": {"items": [1, 2]}')

    assert result.data == {"invoice": {"items": [1, 2]}}
    assert result.repaired_text == '{"invoice": {"items": [1, 2]}}'
    assert result.repair_applied is True
    assert result.repair_attempts == 1
    assert result.strategy_trace == ("close_unterminated_json",)


def test_repair_recovers_with_normalize_single_quotes_only() -> None:
    """Uses only the single-quote strategy when earlier strategies do nothing."""
    result = repair("{'invoice': 1, 'status': 'paid'}")

    assert result.data == {"invoice": 1, "status": "paid"}
    assert result.repaired_text == '{"invoice": 1, "status": "paid"}'
    assert result.repair_applied is True
    assert result.repair_attempts == 1
    assert result.strategy_trace == ("normalize_single_quotes",)


def test_repair_recovers_with_repair_unquoted_keys_only() -> None:
    """Repairs bare object keys after earlier strategies no-op."""
    result = repair('{invoice: 1, status: "paid"}')

    assert result.data == {"invoice": 1, "status": "paid"}
    assert result.repaired_text == '{"invoice": 1, "status": "paid"}'
    assert result.repair_applied is True
    assert result.repair_attempts == 1
    assert result.strategy_trace == ("repair_unquoted_keys",)


def test_repair_recovers_with_multiple_strategies_in_order() -> None:
    """Applies only the required strategies in the documented order."""
    result = repair("{status: 'paid'")

    assert result.data == {"status": "paid"}
    assert result.repaired_text == '{"status": "paid"}'
    assert result.repair_applied is True
    assert result.repair_attempts == 3
    assert result.strategy_trace == (
        "close_unterminated_json",
        "normalize_single_quotes",
        "repair_unquoted_keys",
    )


def test_repair_stops_after_success_without_running_later_strategies() -> None:
    """Stops once parsing succeeds and does not record unnecessary strategies."""
    result = repair('{"items": [1, 2,]')

    assert result.data == {"items": [1, 2]}
    assert result.repaired_text == '{"items": [1, 2]}'
    assert result.repair_applied is True
    assert result.repair_attempts == 2
    assert result.strategy_trace == (
        "remove_trailing_commas",
        "close_unterminated_json",
    )


def test_repair_counts_only_actual_mutation_attempts() -> None:
    """Does not count no-op strategy inspections as repair attempts."""
    result = repair("{'status': 'paid'}")

    assert result.data == {"status": "paid"}
    assert result.repair_attempts == 1
    assert result.strategy_trace == ("normalize_single_quotes",)


def test_repair_respects_max_attempts_limit() -> None:
    """Stops once the configured number of mutations has been attempted."""
    result = repair("{status: 'paid'", max_attempts=2)

    assert result.data is None
    assert result.repaired_text == '{status: "paid"}'
    assert result.repair_applied is True
    assert result.repair_attempts == 2
    assert result.strategy_trace == (
        "close_unterminated_json",
        "normalize_single_quotes",
    )


def test_repair_returns_unrecoverable_result_without_mutation() -> None:
    """Leaves irreparable mismatched structures unchanged."""
    text = '{"items": [1, 2}}'
    result = repair(text)

    assert result.data is None
    assert result.repaired_text == text
    assert result.repair_applied is False
    assert result.repair_attempts == 0
    assert result.strategy_trace == ()


def test_repair_returns_unrecoverable_result_after_mutations() -> None:
    """Returns the final attempted text when repair still cannot parse."""
    result = repair("{status: 'paid'}}", max_attempts=3)

    assert result.data is None
    assert result.repaired_text == '{"status": "paid"}}'
    assert result.repair_applied is True
    assert result.repair_attempts == 2
    assert result.strategy_trace == (
        "normalize_single_quotes",
        "repair_unquoted_keys",
    )


def test_repair_with_zero_max_attempts_skips_strategy_application() -> None:
    """Returns the parse failure state without applying repair strategies."""
    text = "{'status': 'paid'}"
    result = repair(text, max_attempts=0)

    assert result.data is None
    assert result.repaired_text == text
    assert result.repair_applied is False
    assert result.repair_attempts == 0
    assert result.strategy_trace == ()


def test_repair_handles_empty_input() -> None:
    """Returns an unrecoverable result for empty input."""
    result = repair("")

    assert result.data is None
    assert result.repaired_text == ""
    assert result.repair_applied is False
    assert result.repair_attempts == 0
    assert result.strategy_trace == ()


def test_repair_is_idempotent_for_successful_repaired_output() -> None:
    """Produces a valid no-op result when rerun on repaired text."""
    first = repair("{status: 'paid'")
    second = repair(first.repaired_text)

    assert first.data == {"status": "paid"}
    assert second.data == {"status": "paid"}
    assert second.repaired_text == '{"status": "paid"}'
    assert second.repair_applied is False
    assert second.repair_attempts == 0
    assert second.strategy_trace == ()


def test_repair_handles_large_valid_payload_via_fast_path() -> None:
    """Short-circuits a large valid payload without recording repairs."""
    items = ",".join(f'{{"index": {index}, "value": "item-{index}"}}' for index in range(250))
    text = f'{{"items": [{items}]}}'

    result = repair(text)

    assert isinstance(result.data, dict)
    assert result.repaired_text == text
    assert result.repair_applied is False
    assert result.repair_attempts == 0
    assert result.strategy_trace == ()
