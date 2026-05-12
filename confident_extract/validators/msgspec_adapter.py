"""msgspec-based schema validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

import msgspec

T = TypeVar("T", bound=msgspec.Struct)

_MISSING_FIELD_PREFIX = "Object missing required field `"
_PATH_MARKER = " - at `"


@dataclass(frozen=True, slots=True)
class ValidationError:
    """Structured field-level validation error details.

    Attributes:
        message: Human-readable validation message.
        field_path: Path to the failing field, when derivable.
        raw_error: The original `msgspec` validation error string.
    """

    message: str
    field_path: tuple[str, ...]
    raw_error: str


class MsgspecValidationError(Exception):
    """Raised when `msgspec` validation fails."""

    def __init__(self, validation_errors: list[ValidationError], summary: str) -> None:
        """Initializes the validation exception.

        Args:
            validation_errors: Structured validation errors.
            summary: Human-readable summary for exception display.
        """
        super().__init__(summary)
        self.validation_errors = validation_errors
        self.summary = summary


def validate_with_msgspec(data: object, schema: type[T]) -> T:
    """Validates decoded Python objects against a `msgspec.Struct` schema.

    Args:
        data: Decoded Python object to validate.
        schema: Target `msgspec.Struct` schema type.

    Returns:
        A strongly typed schema instance.

    Raises:
        TypeError: If `schema` is not a `msgspec.Struct` subclass.
        MsgspecValidationError: If validation fails.
    """
    if not _is_msgspec_struct_schema(schema):
        message = f"schema must be a msgspec.Struct subclass, got {schema!r}"
        raise TypeError(message)

    if isinstance(data, schema):
        return data

    try:
        return msgspec.convert(data, type=schema, strict=True)
    except msgspec.ValidationError as exc:
        validation_error = _build_validation_error(str(exc))
        summary = _build_summary(schema, validation_error)
        raise MsgspecValidationError([validation_error], summary) from exc


def _build_validation_error(raw_error: str) -> ValidationError:
    message, raw_path = _split_raw_error(raw_error)
    field_path = _parse_field_path(raw_path)
    missing_field = _extract_missing_field_name(message)
    if missing_field is not None and (not field_path or field_path[-1] != missing_field):
        field_path = (*field_path, missing_field)

    return ValidationError(message=message, field_path=field_path, raw_error=raw_error)


def _is_msgspec_struct_schema(schema: object) -> bool:
    return isinstance(schema, type) and issubclass(schema, msgspec.Struct)


def _split_raw_error(raw_error: str) -> tuple[str, str | None]:
    if _PATH_MARKER not in raw_error or not raw_error.endswith("`"):
        return raw_error, None

    path_index = raw_error.rfind(_PATH_MARKER)
    return raw_error[:path_index], raw_error[path_index + len(_PATH_MARKER) : -1]


def _extract_missing_field_name(message: str) -> str | None:
    if not message.startswith(_MISSING_FIELD_PREFIX):
        return None

    end_index = message.find("`", len(_MISSING_FIELD_PREFIX))
    if end_index == -1:
        return None
    return message[len(_MISSING_FIELD_PREFIX) : end_index]


def _parse_field_path(raw_path: str | None) -> tuple[str, ...]:
    if raw_path is None or raw_path == "$":
        return ()

    parts: list[str] = []
    index = 1
    while index < len(raw_path):
        character = raw_path[index]
        if character == ".":
            index += 1
            start = index
            while index < len(raw_path) and raw_path[index] not in ".[":
                index += 1
            if start < index:
                parts.append(raw_path[start:index])
            continue

        if character == "[":
            closing_index = raw_path.find("]", index + 1)
            if closing_index == -1:
                break

            token = raw_path[index + 1 : closing_index]
            if len(token) >= 2 and token[0] in {'"', "'"} and token[-1] == token[0]:
                token = token[1:-1]
            if token:
                parts.append(token)
            index = closing_index + 1
            continue

        index += 1

    return tuple(parts)


def _build_summary(schema: type[msgspec.Struct], error: ValidationError) -> str:
    if not error.field_path:
        return f"{schema.__name__} validation failed: {error.message}"

    return (
        f"{schema.__name__} validation failed at "
        f"{_format_field_path(error.field_path)}: {error.message}"
    )


def _format_field_path(field_path: tuple[str, ...]) -> str:
    formatted: list[str] = []
    for part in field_path:
        if not formatted:
            formatted.append(part)
            continue

        if part.isdigit() or part == "...":
            formatted[-1] = f"{formatted[-1]}[{part}]"
            continue

        formatted.append(part)

    return ".".join(formatted)
