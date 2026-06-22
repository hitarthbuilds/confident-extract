"""Tests for the three new repair strategies."""

from __future__ import annotations

from confident_extract.repair.strategies import (
    extract_json_from_prose,
    fix_python_literals,
    strip_json_comments,
)

# ---------------------------------------------------------------------------
# strip_json_comments
# ---------------------------------------------------------------------------


class TestStripJsonComments:
    def test_no_comments_unchanged(self) -> None:
        text = '{"key": "value"}'
        assert strip_json_comments(text) == text

    def test_removes_line_comment(self) -> None:
        text = '{"key": "value" // this is a comment\n}'
        result = strip_json_comments(text)
        assert "//" not in result
        assert '"key"' in result

    def test_removes_block_comment(self) -> None:
        text = '{"key": /* inline */ "value"}'
        result = strip_json_comments(text)
        assert "/*" not in result
        assert '"key"' in result
        assert '"value"' in result

    def test_preserves_comment_inside_string(self) -> None:
        text = '{"url": "http://example.com"}'
        result = strip_json_comments(text)
        assert result == text

    def test_multiline_block_comment(self) -> None:
        text = '{\n/* this is\na block comment */\n"k": 1\n}'
        result = strip_json_comments(text)
        assert "/*" not in result
        assert '"k"' in result

    def test_fast_path_no_slash(self) -> None:
        text = '{"a": 1, "b": 2}'
        assert strip_json_comments(text) is text


# ---------------------------------------------------------------------------
# fix_python_literals
# ---------------------------------------------------------------------------


class TestFixPythonLiterals:
    def test_no_literals_unchanged(self) -> None:
        text = '{"active": true, "count": null}'
        assert fix_python_literals(text) is text

    def test_replaces_true(self) -> None:
        text = '{"active": True}'
        result = fix_python_literals(text)
        assert '"active": true' in result

    def test_replaces_false(self) -> None:
        text = '{"active": False}'
        result = fix_python_literals(text)
        assert '"active": false' in result

    def test_replaces_none(self) -> None:
        text = '{"value": None}'
        result = fix_python_literals(text)
        assert '"value": null' in result

    def test_preserves_literals_inside_strings(self) -> None:
        text = '{"label": "NoneType", "flag": True}'
        result = fix_python_literals(text)
        assert '"NoneType"' in result
        assert '"flag": true' in result

    def test_all_three_replaced(self) -> None:
        text = '{"a": True, "b": False, "c": None}'
        result = fix_python_literals(text)
        assert "true" in result
        assert "false" in result
        assert "null" in result
        assert "True" not in result
        assert "False" not in result
        assert "None" not in result

    def test_word_boundary_respected(self) -> None:
        text = '{"TrueColor": 1}'
        result = fix_python_literals(text)
        assert "TrueColor" in result

    def test_fast_path_no_capitals(self) -> None:
        text = '{"active": true}'
        assert fix_python_literals(text) is text


# ---------------------------------------------------------------------------
# extract_json_from_prose
# ---------------------------------------------------------------------------


class TestExtractJsonFromProse:
    def test_bare_json_unchanged(self) -> None:
        text = '{"key": "value"}'
        assert extract_json_from_prose(text) == text

    def test_extracts_object_from_prose(self) -> None:
        text = 'Here is the result: {"id": 1, "status": "ok"} — done.'
        result = extract_json_from_prose(text)
        assert result == '{"id": 1, "status": "ok"}'

    def test_extracts_array_from_prose(self) -> None:
        text = 'The list is [1, 2, 3] as requested.'
        result = extract_json_from_prose(text)
        assert result == "[1, 2, 3]"

    def test_no_json_unchanged(self) -> None:
        text = "No JSON here at all."
        assert extract_json_from_prose(text) == text

    def test_nested_object_extracted_correctly(self) -> None:
        text = 'Output: {"a": {"b": 2}} end'
        result = extract_json_from_prose(text)
        assert result == '{"a": {"b": 2}}'

    def test_object_preferred_when_both_present(self) -> None:
        text = 'obj: {"x": 1} arr: [2, 3]'
        result = extract_json_from_prose(text)
        assert result == '{"x": 1}'

    def test_brace_inside_string_not_confused(self) -> None:
        text = 'result: {"msg": "use {name} format"}'
        result = extract_json_from_prose(text)
        assert result == '{"msg": "use {name} format"}'
