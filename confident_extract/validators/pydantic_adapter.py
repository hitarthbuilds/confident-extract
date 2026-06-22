"""Pydantic v2 schema validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PydanticFieldError:
    """Structured field-level error from Pydantic validation.

    Attributes:
        message: Human-readable validation message.
        field_path: Path to the failing field as a tuple of string segments.
        raw_error: The original Pydantic error dict as a string.
    """

    message: str
    field_path: tuple[str, ...]
    raw_error: str


class PydanticValidationError(Exception):
    """Raised when Pydantic validation fails during extraction."""

    def __init__(self, validation_errors: list[PydanticFieldError], summary: str) -> None:
        """Initialises the error with structured field errors and a summary message."""
        super().__init__(summary)
        self.validation_errors = validation_errors
        self.summary = summary


def is_pydantic_model(schema: object) -> bool:
    """Returns True when *schema* is a Pydantic v2 BaseModel subclass."""
    try:
        from pydantic import BaseModel

        return isinstance(schema, type) and issubclass(schema, BaseModel)
    except ImportError:
        return False


def validate_with_pydantic(data: object, schema: type[T]) -> T:
    """Validates a decoded Python object against a Pydantic v2 BaseModel schema.

    Args:
        data: Decoded Python object (dict, list, or primitive) to validate.
        schema: Target Pydantic BaseModel subclass.

    Returns:
        A strongly typed ``schema`` instance.

    Raises:
        ImportError: If pydantic is not installed.
        PydanticValidationError: If validation fails.
    """
    try:
        from pydantic import BaseModel
        from pydantic import ValidationError as _PydanticError
    except ImportError as exc:
        msg = (
            "pydantic is required to validate Pydantic models. "
            "Install it with: pip install 'confident-extract[pydantic]'"
        )
        raise ImportError(msg) from exc

    if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
        msg = f"schema must be a pydantic.BaseModel subclass, got {schema!r}"
        raise TypeError(msg)

    try:
        return schema.model_validate(data)  # type: ignore[return-value]
    except _PydanticError as exc:
        errors = [
            PydanticFieldError(
                message=e["msg"],
                field_path=tuple(str(loc) for loc in e["loc"]),
                raw_error=str(e),
            )
            for e in exc.errors()
        ]
        first_msg = errors[0].message if errors else str(exc)
        summary = f"{schema.__name__} validation failed: {first_msg}"
        raise PydanticValidationError(errors, summary) from exc
