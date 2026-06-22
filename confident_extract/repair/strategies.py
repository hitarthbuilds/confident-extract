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


def strip_json_comments(text: str) -> str:
    """Removes C-style // line comments and /* block comments from JSON-like text.

    Args:
        text: JSON-like text that may contain JavaScript-style comments.

    Returns:
        The input with all // and /* ... */ comments removed, leaving string
        content intact. Returns the input unchanged if no comment markers are present.
    """
    if "//" not in text and "/*" not in text:
        return text

    output: list[str] = []
    in_string = False
    escaped = False
    index = 0
    length = len(text)

    while index < length:
        character = text[index]

        if in_string:
            output.append(character)
            if escaped:
                escaped = False
            elif character == _BACKSLASH:
                escaped = True
            elif character == _DOUBLE_QUOTE:
                in_string = False
            index += 1
            continue

        if character == _DOUBLE_QUOTE:
            in_string = True
            output.append(character)
            index += 1
            continue

        if character == "/" and index + 1 < length:
            next_character = text[index + 1]

            if next_character == "/":
                index += 2
                while index < length and text[index] != "\n":
                    index += 1
                continue

            if next_character == "*":
                index += 2
                while index < length:
                    if text[index] == "*" and index + 1 < length and text[index + 1] == "/":
                        index += 2
                        break
                    index += 1
                continue

        output.append(character)
        index += 1

    result = "".join(output)
    return result if result != text else text


def fix_python_literals(text: str) -> str:
    """Replaces Python True, False, and None with JSON-valid true, false, and null.

    Args:
        text: JSON-like text that may contain Python boolean or None literals.

    Returns:
        The input with Python literals replaced by their JSON equivalents.
        String content is left intact. Returns the input unchanged if no
        Python literals are present outside of strings.
    """
    if "True" not in text and "False" not in text and "None" not in text:
        return text

    output: list[str] = []
    in_string = False
    current_quote = ""
    escaped = False
    index = 0
    length = len(text)
    mutated = False

    while index < length:
        character = text[index]

        if in_string:
            output.append(character)
            if escaped:
                escaped = False
            elif character == _BACKSLASH:
                escaped = True
            elif character == current_quote:
                in_string = False
            index += 1
            continue

        if character in (_DOUBLE_QUOTE, _SINGLE_QUOTE):
            in_string = True
            current_quote = character
            output.append(character)
            index += 1
            continue

        if character == "T" and text[index : index + 4] == "True":
            tail = index + 4
            if tail >= length or not (text[tail].isalnum() or text[tail] == "_"):
                output.append("true")
                index = tail
                mutated = True
                continue

        if character == "F" and text[index : index + 5] == "False":
            tail = index + 5
            if tail >= length or not (text[tail].isalnum() or text[tail] == "_"):
                output.append("false")
                index = tail
                mutated = True
                continue

        if character == "N" and text[index : index + 4] == "None":
            tail = index + 4
            if tail >= length or not (text[tail].isalnum() or text[tail] == "_"):
                output.append("null")
                index = tail
                mutated = True
                continue

        output.append(character)
        index += 1

    if not mutated:
        return text
    return "".join(output)


def extract_json_from_prose(text: str) -> str:
    """Extracts the first balanced JSON object or array from surrounding prose.

    Args:
        text: Raw text that may contain a JSON payload embedded in prose,
            instructions, or other non-JSON content.

    Returns:
        The extracted JSON substring when a balanced object or array is found
        at or after the first brace or bracket. Returns the input unchanged when
        no valid JSON container is found or when the input is already bare JSON.
    """
    first_brace = text.find(_OBJECT_OPEN)
    first_bracket = text.find(_ARRAY_OPEN)

    if first_brace == -1 and first_bracket == -1:
        return text

    if first_brace == -1:
        start = first_bracket
        opener, closer = _ARRAY_OPEN, _ARRAY_CLOSE
    elif first_bracket == -1:
        start = first_brace
        opener, closer = _OBJECT_OPEN, _OBJECT_CLOSE
    elif first_brace <= first_bracket:
        start = first_brace
        opener, closer = _OBJECT_OPEN, _OBJECT_CLOSE
    else:
        start = first_bracket
        opener, closer = _ARRAY_OPEN, _ARRAY_CLOSE

    if start == 0 and text.endswith(closer):
        return text

    depth = 0
    in_string = False
    escaped = False
    index = start

    while index < len(text):
        character = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif character == _BACKSLASH:
                escaped = True
            elif character == _DOUBLE_QUOTE:
                in_string = False
            index += 1
            continue

        if character == _DOUBLE_QUOTE:
            in_string = True
        elif character == opener:
            depth += 1
        elif character == closer:
            depth -= 1
            if depth == 0:
                candidate = text[start : index + 1]
                return candidate if candidate != text else text

        index += 1

    return text
