"""Unit tests for preprocessing helpers."""

from __future__ import annotations

from confident_extract.core.preprocessor import (
    normalize_whitespace,
    preprocess,
    strip_markdown_fences,
    unwrap_escaped_json,
)


def test_strip_markdown_fences_removes_json_fence_and_preserves_formatting() -> None:
    """Strips a `json` fence while preserving inner indentation and newlines."""
    text = '```json\n{\n  "invoice": 1,\n  "items": [\n    1,\n    2\n  ]\n}\n```'

    assert strip_markdown_fences(text) == '{\n  "invoice": 1,\n  "items": [\n    1,\n    2\n  ]\n}'


def test_strip_markdown_fences_removes_plain_fence_with_outer_whitespace() -> None:
    """Strips a plain fence even when outer whitespace surrounds the block."""
    text = ' \n\t```\n{"ok": true}\n```\n '

    assert strip_markdown_fences(text) == '{"ok": true}'


def test_strip_markdown_fences_leaves_unclosed_fence_unchanged() -> None:
    """Leaves malformed fenced input unchanged."""
    text = '```json\n{"ok": true}'

    assert strip_markdown_fences(text) == text


def test_strip_markdown_fences_leaves_unsupported_language_unchanged() -> None:
    """Leaves unsupported fenced languages unchanged for deterministic behavior."""
    text = '```python\n{"ok": true}\n```'

    assert strip_markdown_fences(text) == text


def test_strip_markdown_fences_handles_empty_input() -> None:
    """Returns empty input unchanged."""
    assert strip_markdown_fences("") == ""


def test_strip_markdown_fences_handles_empty_fenced_payload() -> None:
    """Returns an empty payload for an otherwise valid empty fenced block."""
    assert strip_markdown_fences("```json\n```") == ""


def test_normalize_whitespace_normalizes_crlf_and_outer_whitespace() -> None:
    """Normalizes line endings and trims only outer whitespace."""
    text = ' \r\n{\r\n  "message": "line 1\\r\\nline 2"\r\n}\r\n '

    assert normalize_whitespace(text) == '{\n  "message": "line 1\\r\\nline 2"\n}'


def test_normalize_whitespace_preserves_internal_string_spaces() -> None:
    """Preserves whitespace contained inside JSON string values."""
    text = '\n{"message": "  keep   this  "}\n'

    assert normalize_whitespace(text) == '{"message": "  keep   this  "}'


def test_normalize_whitespace_handles_empty_input() -> None:
    """Returns empty input unchanged."""
    assert normalize_whitespace("") == ""


def test_normalize_whitespace_is_idempotent() -> None:
    """Produces the same result when applied repeatedly."""
    text = '{\n  "value": 1\n}'

    assert normalize_whitespace(normalize_whitespace(text)) == text


def test_unwrap_escaped_json_unwraps_single_escaped_object() -> None:
    """Unwraps a JSON object stored inside a JSON string literal."""
    text = '"{\\"invoice\\":1,\\"status\\":\\"paid\\"}"'

    assert unwrap_escaped_json(text) == '{"invoice":1,"status":"paid"}'


def test_unwrap_escaped_json_unwraps_double_escaped_object() -> None:
    """Unwraps nested JSON string escaping deterministically."""
    text = '"\\"{\\\\\\"invoice\\\\\\":1,\\\\\\"status\\\\\\":\\\\\\"paid\\\\\\"}\\""'

    assert unwrap_escaped_json(text) == '{"invoice":1,"status":"paid"}'


def test_unwrap_escaped_json_leaves_plain_json_string_unchanged() -> None:
    """Avoids unwrapping strings that are not JSON payloads."""
    text = '"not actually json"'

    assert unwrap_escaped_json(text) == text


def test_unwrap_escaped_json_leaves_malformed_input_unchanged() -> None:
    """Leaves malformed escaped JSON unchanged instead of guessing."""
    text = '"{\\"invoice\\":1'

    assert unwrap_escaped_json(text) == text


def test_unwrap_escaped_json_handles_empty_input() -> None:
    """Returns empty input unchanged."""
    assert unwrap_escaped_json("") == ""


def test_unwrap_escaped_json_is_idempotent() -> None:
    """Produces the same result when called on already unwrapped JSON."""
    text = '{"invoice":1}'

    assert unwrap_escaped_json(unwrap_escaped_json(text)) == text


def test_preprocess_composes_helpers_for_fenced_escaped_json() -> None:
    """Runs fence stripping, whitespace normalization, and unwrapping in order."""
    text = ' \r\n```json\r\n"{\\"invoice\\": 1, \\"status\\": \\"paid\\"}"\r\n```\r\n '

    assert preprocess(text) == '{"invoice": 1, "status": "paid"}'


def test_preprocess_normalizes_malformed_unclosed_fence_without_guessing() -> None:
    """Normalizes whitespace but does not invent a closing fence."""
    text = ' \r\n```json\r\n{"invoice": 1}\r\n '

    assert preprocess(text) == '```json\n{"invoice": 1}'


def test_preprocess_handles_empty_input() -> None:
    """Returns empty input unchanged."""
    assert preprocess("") == ""


def test_preprocess_is_idempotent_for_clean_json() -> None:
    """Leaves already clean JSON unchanged across repeated calls."""
    text = '{"invoice": 1, "status": "paid"}'

    assert preprocess(preprocess(text)) == text
