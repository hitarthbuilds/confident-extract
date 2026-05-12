"""Unit tests for pure JSON repair strategies."""

from __future__ import annotations

from confident_extract.repair.strategies import (
    close_unterminated_json,
    normalize_single_quotes,
    remove_trailing_commas,
    repair_unquoted_keys,
    try_orjson_parse,
)


def test_try_orjson_parse_returns_parsed_object_for_valid_json() -> None:
    """Parses valid JSON without raising."""
    parsed, success = try_orjson_parse('{"invoice": 1, "paid": true}')

    assert success is True
    assert parsed == {"invoice": 1, "paid": True}


def test_try_orjson_parse_treats_json_null_as_success() -> None:
    """Distinguishes parsed `null` from a decode failure."""
    parsed, success = try_orjson_parse("null")

    assert success is True
    assert parsed is None


def test_try_orjson_parse_returns_failure_for_invalid_json() -> None:
    """Returns a failure flag instead of propagating decode errors."""
    parsed, success = try_orjson_parse('{"invoice": 1')

    assert success is False
    assert parsed is None


def test_try_orjson_parse_returns_failure_for_empty_input() -> None:
    """Returns a failure for empty input."""
    assert try_orjson_parse("") == (None, False)


def test_remove_trailing_commas_repairs_objects_and_arrays() -> None:
    """Removes trailing commas before object and array closers."""
    text = '{"invoice": 1, "items": [1, 2,], "meta": {"paid": true,},}'

    assert remove_trailing_commas(text) == '{"invoice": 1, "items": [1, 2], "meta": {"paid": true}}'


def test_remove_trailing_commas_preserves_commas_inside_strings() -> None:
    """Leaves commas inside quoted content untouched."""
    text = '{"message": "keep, this, exactly, as-is,}", "items": [1, 2,],}'
    expected = '{"message": "keep, this, exactly, as-is,}", "items": [1, 2]}'

    assert remove_trailing_commas(text) == expected


def test_remove_trailing_commas_leaves_valid_json_unchanged() -> None:
    """Returns already valid JSON unchanged."""
    text = '{"invoice": 1, "items": [1, 2]}'

    assert remove_trailing_commas(text) == text


def test_remove_trailing_commas_is_idempotent() -> None:
    """Produces the same result when called repeatedly."""
    text = '{"invoice": 1, "items": [1, 2,],}'
    repaired = remove_trailing_commas(text)

    assert remove_trailing_commas(repaired) == repaired


def test_remove_trailing_commas_handles_empty_input() -> None:
    """Returns empty input unchanged."""
    assert remove_trailing_commas("") == ""


def test_close_unterminated_json_closes_nested_objects_and_arrays() -> None:
    """Appends only the missing closers for truncated nested containers."""
    text = '{"invoice": {"items": [1, 2, {"paid": true}'

    assert close_unterminated_json(text) == '{"invoice": {"items": [1, 2, {"paid": true}]}}'


def test_close_unterminated_json_ignores_braces_inside_strings() -> None:
    """Does not count braces or brackets embedded inside strings."""
    text = '{"message": "brace } and bracket ] here", "items": [1, 2'
    expected = '{"message": "brace } and bracket ] here", "items": [1, 2]}'

    assert close_unterminated_json(text) == expected


def test_close_unterminated_json_leaves_balanced_json_unchanged() -> None:
    """Does not append extra closers to already balanced JSON."""
    text = '{"invoice": {"items": [1, 2]}}'

    assert close_unterminated_json(text) == text


def test_close_unterminated_json_leaves_mismatched_closers_unchanged() -> None:
    """Avoids guessing when the structure is not a simple truncation."""
    text = '{"invoice": [1, 2}}'

    assert close_unterminated_json(text) == text


def test_close_unterminated_json_leaves_unterminated_strings_unchanged() -> None:
    """Avoids appending closers when a string literal is still open."""
    text = '{"message": "unterminated", "tail": "value}'

    assert close_unterminated_json(text) == text


def test_close_unterminated_json_handles_empty_input() -> None:
    """Returns empty input unchanged."""
    assert close_unterminated_json("") == ""


def test_close_unterminated_json_is_idempotent() -> None:
    """Produces the same result when called repeatedly."""
    text = '{"invoice": [1, 2'
    repaired = close_unterminated_json(text)

    assert close_unterminated_json(repaired) == repaired


def test_normalize_single_quotes_converts_keys_and_values() -> None:
    """Converts JSON-like single-quoted keys and values into JSON strings."""
    text = "{'invoice': 1, 'status': 'paid'}"

    assert normalize_single_quotes(text) == '{"invoice": 1, "status": "paid"}'


def test_normalize_single_quotes_handles_nested_structures() -> None:
    """Converts nested single-quoted objects and arrays."""
    text = "{'invoice': {'lines': ['a', 'b']}, 'paid': true}"

    assert normalize_single_quotes(text) == '{"invoice": {"lines": ["a", "b"]}, "paid": true}'


def test_normalize_single_quotes_preserves_apostrophes_inside_content() -> None:
    """Keeps apostrophes that are part of the content rather than delimiters."""
    text = "{'message': 'don\\'t stop believing', 'owner': 'teacher\\'s pet'}"
    expected = '{"message": "don\'t stop believing", "owner": "teacher\'s pet"}'

    assert normalize_single_quotes(text) == expected


def test_normalize_single_quotes_escapes_embedded_double_quotes() -> None:
    """Escapes embedded double quotes when converting a single-quoted string."""
    text = "{'message': 'say \"hello\"'}"

    assert normalize_single_quotes(text) == '{"message": "say \\"hello\\""}'


def test_normalize_single_quotes_leaves_double_quoted_json_unchanged() -> None:
    """Preserves already valid double-quoted JSON."""
    text = '{"message": "don\'t change this"}'

    assert normalize_single_quotes(text) == text


def test_normalize_single_quotes_leaves_unmatched_single_quotes_unchanged() -> None:
    """Avoids partial rewrites when a single-quoted string never closes."""
    text = "{'message': 'unterminated}"

    assert normalize_single_quotes(text) == text


def test_normalize_single_quotes_handles_empty_input() -> None:
    """Returns empty input unchanged."""
    assert normalize_single_quotes("") == ""


def test_normalize_single_quotes_is_idempotent() -> None:
    """Produces the same result when called repeatedly."""
    text = "{'invoice': 1, 'status': 'paid'}"
    repaired = normalize_single_quotes(text)

    assert normalize_single_quotes(repaired) == repaired


def test_repair_unquoted_keys_quotes_common_bare_keys() -> None:
    """Quotes common unquoted keys in nested objects."""
    text = '{invoice_id: 1, status: "paid", nested_value: {line_items: [1, 2]}}'
    expected = (
        '{"invoice_id": 1, "status": "paid", '
        '"nested_value": {"line_items": [1, 2]}}'
    )

    assert repair_unquoted_keys(text) == expected


def test_repair_unquoted_keys_preserves_strings_containing_colons_and_braces() -> None:
    """Does not quote content that only looks like keys inside strings."""
    text = '{message: "keep {this: value} literal", nested: {status: "paid"}}'
    expected = (
        '{"message": "keep {this: value} literal", '
        '"nested": {"status": "paid"}}'
    )

    assert repair_unquoted_keys(text) == expected


def test_repair_unquoted_keys_leaves_valid_json_unchanged() -> None:
    """Leaves already quoted keys unchanged."""
    text = '{"invoice_id": 1, "status": "paid"}'

    assert repair_unquoted_keys(text) == text


def test_repair_unquoted_keys_leaves_non_object_values_unchanged() -> None:
    """Does not treat array values as object keys."""
    text = '[invoice_id, {"status": "paid"}]'

    assert repair_unquoted_keys(text) == text


def test_repair_unquoted_keys_handles_empty_input() -> None:
    """Returns empty input unchanged."""
    assert repair_unquoted_keys("") == ""


def test_repair_unquoted_keys_is_idempotent() -> None:
    """Produces the same result when called repeatedly."""
    text = "{invoice_id: 1, nested_value: {status: 'paid'}}"
    repaired = repair_unquoted_keys(text)

    assert repair_unquoted_keys(repaired) == repaired
