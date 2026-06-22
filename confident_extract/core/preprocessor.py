"""Preprocessing utilities for JSON-like model output."""

from __future__ import annotations

import orjson

_MARKDOWN_FENCE = "```"


def strip_markdown_fences(text: str) -> str:
    """Removes a supported outer Markdown code fence from the input.

    Args:
        text: Raw text that may be wrapped in a fenced code block.

    Returns:
        The fenced payload when the entire input is wrapped in a plain or
        ``json``-tagged Markdown fence. Otherwise returns the input unchanged.
    """
    if _MARKDOWN_FENCE not in text:
        return text

    candidate = text.strip()
    if not candidate.startswith(_MARKDOWN_FENCE) or not candidate.endswith(_MARKDOWN_FENCE):
        return text

    opening_end = candidate.find("\n")
    if opening_end == -1:
        return text

    header = candidate[len(_MARKDOWN_FENCE) : opening_end].strip().lower()
    if header not in {"", "json"}:
        return text

    closing_start = candidate.rfind(f"\n{_MARKDOWN_FENCE}")
    if closing_start < opening_end or candidate[closing_start + 1 :] != _MARKDOWN_FENCE:
        return text

    return candidate[opening_end + 1 : closing_start]


def normalize_whitespace(text: str) -> str:
    """Normalizes line endings and trims outer whitespace.

    Args:
        text: Raw or partially normalized JSON-like text.

    Returns:
        A string with CRLF and CR normalized to LF and leading or trailing
        whitespace removed. Internal whitespace is preserved.
    """
    normalized = text
    if "\r" in normalized:
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    stripped = normalized.strip()
    if stripped != normalized:
        return stripped
    return normalized


def unwrap_escaped_json(text: str) -> str:
    """Unwraps escaped JSON payloads stored inside JSON string literals.

    Args:
        text: JSON-like text that may itself be encoded as a JSON string.

    Returns:
        The unwrapped JSON payload when the input is a quoted JSON string whose
        decoded value is another JSON container or nested JSON string.
        Otherwise returns the input unchanged.
    """
    current = text

    for _ in range(3):
        if len(current) < 2 or current[0] != '"' or current[-1] != '"':
            return current

        try:
            decoded = orjson.loads(current)
        except orjson.JSONDecodeError:
            return current

        if not isinstance(decoded, str):
            return current

        candidate = decoded.strip()
        if not _looks_like_json_payload(candidate):
            return current

        current = candidate

    return current


def preprocess(text: str) -> str:
    """Applies the full preprocessing pipeline to raw model output.

    Includes a fast path for bare JSON input that skips Markdown fence
    stripping and escaped-JSON unwrapping, as those operations are only
    relevant when the input is wrapped in a fence or a quoted string literal.

    Args:
        text: Raw model output that may contain Markdown fences, outer
            whitespace, or escaped JSON.

    Returns:
        Cleaned text ready for the repair and validation stages.
    """
    # Fast path: no fence marker and no CRLF → just strip whitespace.
    # Escaped-JSON unwrapping is only needed when the text starts with '"'.
    if _MARKDOWN_FENCE not in text and "\r" not in text:
        stripped = text.strip()
        if not stripped or stripped[0] != '"':
            return stripped
        # Could be escaped JSON — unwrap and re-strip if it changed.
        unwrapped = unwrap_escaped_json(stripped)
        if unwrapped is stripped:
            return stripped
        return unwrapped.strip() if unwrapped != stripped else stripped

    # Full pipeline: fences, CRLF normalization, and optional escape unwrapping.
    normalized = normalize_whitespace(strip_markdown_fences(text))
    unwrapped = unwrap_escaped_json(normalized)
    if unwrapped is normalized or unwrapped == normalized:
        return normalized
    return normalize_whitespace(unwrapped)


def _looks_like_json_payload(text: str) -> bool:
    """Checks whether a string looks like a JSON payload worth unwrapping."""
    if len(text) < 2:
        return False

    first = text[0]
    last = text[-1]
    return (first == "{" and last == "}") or (first == "[" and last == "]") or (
        first == '"' and last == '"'
    )
