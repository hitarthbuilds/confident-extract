"""Pure repair strategies for malformed JSON-like text."""

from __future__ import annotations

import orjson

_OBJECT_OPEN = "{"
_OBJECT_CLOSE = "}"
_ARRAY_OPEN = "["
_ARRAY_CLOSE = "]"
_DOUBLE_QUOTE = '"'
_SINGLE_QUOTE = "'"
_BACKSLASH = "\\"

_SINGLE_QUOTED_ESCAPES = {
    _DOUBLE_QUOTE: _DOUBLE_QUOTE,
    _SINGLE_QUOTE: _SINGLE_QUOTE,
    _BACKSLASH: _BACKSLASH,
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


def try_orjson_parse(text: str) -> tuple[object | None, bool]:
    """Attempts a raw `orjson` parse without surfacing decode errors.

    Args:
        text: Candidate JSON text.

    Returns:
        A tuple of `(parsed_value, success)`. On decode failure, returns
        `(None, False)`. Successful parsing of JSON `null` returns `(None, True)`.
    """
    if not text:
        return None, False

    try:
        return orjson.loads(text), True
    except orjson.JSONDecodeError:
        return None, False


def remove_trailing_commas(text: str) -> str:
    """Removes trailing commas before object or array closers.

    Args:
        text: JSON-like text that may contain trailing commas.

    Returns:
        The repaired text with commas immediately before `}` or `]` removed,
        while leaving commas inside quoted strings untouched.
    """
    if "," not in text:
        return text

    output: list[str] | None = None
    in_string = False
    current_quote = ""
    escaped = False

    for index, character in enumerate(text):
        if in_string:
            if output is not None:
                output.append(character)

            if escaped:
                escaped = False
            elif character == _BACKSLASH:
                escaped = True
            elif character == current_quote:
                in_string = False
            continue

        if character == _DOUBLE_QUOTE or character == _SINGLE_QUOTE:
            in_string = True
            current_quote = character
            if output is not None:
                output.append(character)
            continue

        if character != ",":
            if output is not None:
                output.append(character)
            continue

        lookahead = index + 1
        while lookahead < len(text) and text[lookahead].isspace():
            lookahead += 1

        if lookahead < len(text) and text[lookahead] in {_OBJECT_CLOSE, _ARRAY_CLOSE}:
            if output is None:
                output = [text[:index]]
            continue

        if output is not None:
            output.append(character)

    if output is None:
        return text
    return "".join(output)


def close_unterminated_json(text: str) -> str:
    """Appends missing object or array closers for truncated JSON containers.

    Args:
        text: JSON-like text that may be missing closing braces or brackets.

    Returns:
        The input with only the missing closing braces or brackets appended.
        Already balanced or structurally mismatched inputs are returned unchanged.
    """
    if _OBJECT_OPEN not in text and _ARRAY_OPEN not in text:
        return text

    expected_closers: list[str] = []
    in_string = False
    current_quote = ""
    escaped = False

    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == _BACKSLASH:
                escaped = True
            elif character == current_quote:
                in_string = False
            continue

        if character == _DOUBLE_QUOTE or character == _SINGLE_QUOTE:
            in_string = True
            current_quote = character
            continue

        if character == _OBJECT_OPEN:
            expected_closers.append(_OBJECT_CLOSE)
            continue

        if character == _ARRAY_OPEN:
            expected_closers.append(_ARRAY_CLOSE)
            continue

        if character == _OBJECT_CLOSE or character == _ARRAY_CLOSE:
            if not expected_closers or expected_closers[-1] != character:
                return text
            expected_closers.pop()

    if in_string or not expected_closers:
        return text

    return text + "".join(reversed(expected_closers))


def normalize_single_quotes(text: str) -> str:
    """Normalizes JSON-like single-quoted strings into double-quoted JSON.

    Args:
        text: JSON-like text that may use single quotes for keys or values.

    Returns:
        The input with single-quoted strings converted to JSON-compatible
        double-quoted strings. Unrecoverable unmatched quotes are returned
        unchanged.
    """
    if _SINGLE_QUOTE not in text:
        return text

    output: list[str] = []
    in_double = False
    double_escaped = False
    in_single = False
    single_content: list[str] = []
    index = 0

    while index < len(text):
        character = text[index]

        if in_single:
            if character == _BACKSLASH:
                decoded_escape, next_index = _decode_single_quoted_escape(text, index)
                single_content.append(decoded_escape)
                index = next_index
                continue

            if character == _SINGLE_QUOTE and _is_single_quote_terminator(text, index):
                output.append(orjson.dumps("".join(single_content)).decode("utf-8"))
                single_content = []
                in_single = False
                index += 1
                continue

            single_content.append(character)
            index += 1
            continue

        if in_double:
            output.append(character)
            if double_escaped:
                double_escaped = False
            elif character == _BACKSLASH:
                double_escaped = True
            elif character == _DOUBLE_QUOTE:
                in_double = False
            index += 1
            continue

        if character == _DOUBLE_QUOTE:
            in_double = True
            output.append(character)
            index += 1
            continue

        if character == _SINGLE_QUOTE:
            in_single = True
            single_content = []
            index += 1
            continue

        output.append(character)
        index += 1

    if in_single or in_double:
        return text

    normalized = "".join(output)
    if normalized == text:
        return text
    return normalized


def repair_unquoted_keys(text: str) -> str:
    """Quotes common bare object keys without changing valid JSON keys.

    Args:
        text: JSON-like text that may contain unquoted object keys.

    Returns:
        The input with recognized unquoted object keys wrapped in double quotes.
        Inputs that do not match the supported key pattern are left unchanged.
    """
    if ":" not in text or _OBJECT_OPEN not in text:
        return text

    output: list[str] | None = None
    container_stack: list[str] = []
    key_expected_stack: list[bool] = []
    in_string = False
    current_quote = ""
    escaped = False
    index = 0

    while index < len(text):
        character = text[index]

        if in_string:
            if output is not None:
                output.append(character)

            if escaped:
                escaped = False
            elif character == _BACKSLASH:
                escaped = True
            elif character == current_quote:
                in_string = False

            index += 1
            continue

        if character == _DOUBLE_QUOTE or character == _SINGLE_QUOTE:
            in_string = True
            current_quote = character
            if output is not None:
                output.append(character)
            index += 1
            continue

        if (
            container_stack
            and container_stack[-1] == _OBJECT_OPEN
            and key_expected_stack[-1]
            and _is_unquoted_key_start(character)
        ):
            key_end = index + 1
            while key_end < len(text) and _is_unquoted_key_continue(text[key_end]):
                key_end += 1

            lookahead = key_end
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1

            if lookahead < len(text) and text[lookahead] == ":":
                if output is None:
                    output = [text[:index]]
                output.append(_DOUBLE_QUOTE)
                output.append(text[index:key_end])
                output.append(_DOUBLE_QUOTE)
                index = key_end
                continue

        if character == _OBJECT_OPEN:
            container_stack.append(_OBJECT_OPEN)
            key_expected_stack.append(True)
        elif character == _ARRAY_OPEN:
            container_stack.append(_ARRAY_OPEN)
            key_expected_stack.append(False)
        elif character == ":":
            if container_stack and container_stack[-1] == _OBJECT_OPEN:
                key_expected_stack[-1] = False
        elif character == ",":
            if container_stack and container_stack[-1] == _OBJECT_OPEN:
                key_expected_stack[-1] = True
        elif character == _OBJECT_CLOSE or character == _ARRAY_CLOSE:
            if container_stack:
                container_stack.pop()
                key_expected_stack.pop()

        if output is not None:
            output.append(character)

        index += 1

    if output is None:
        return text
    return "".join(output)


def _decode_single_quoted_escape(text: str, start: int) -> tuple[str, int]:
    if start + 1 >= len(text):
        return _BACKSLASH, start + 1

    escaped = text[start + 1]
    replacement = _SINGLE_QUOTED_ESCAPES.get(escaped)
    if replacement is not None:
        return replacement, start + 2

    if escaped == "u" and start + 5 < len(text):
        codepoint = text[start + 2 : start + 6]
        if all(_is_hex_digit(character) for character in codepoint):
            return chr(int(codepoint, 16)), start + 6

    return _BACKSLASH + escaped, start + 2


def _is_hex_digit(character: str) -> bool:
    return character.isdigit() or character.lower() in {"a", "b", "c", "d", "e", "f"}


def _is_single_quote_terminator(text: str, index: int) -> bool:
    lookahead = index + 1
    while lookahead < len(text) and text[lookahead].isspace():
        lookahead += 1

    if lookahead >= len(text):
        return True

    return text[lookahead] in {":", ",", _OBJECT_CLOSE, _ARRAY_CLOSE}


def _is_unquoted_key_start(character: str) -> bool:
    return character.isalpha() or character in {"_", "$"}


def _is_unquoted_key_continue(character: str) -> bool:
    return character.isalnum() or character in {"_", "-", "$"}
