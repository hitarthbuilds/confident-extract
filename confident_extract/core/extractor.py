"""Synchronous and asynchronous extraction pipeline."""

from __future__ import annotations

import dataclasses
import time
from typing import TypeVar

import msgspec

from confident_extract.confidence.scorer import compute_confidence
from confident_extract.core.preprocessor import preprocess
from confident_extract.core.result import ExtractionResult
from confident_extract.repair.engine import repair
from confident_extract.repair.strategies import try_orjson_parse
from confident_extract.validators.msgspec_adapter import validate_with_msgspec
from confident_extract.validators.pydantic_adapter import (
    is_pydantic_model,
    validate_with_pydantic,
)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Schema-kind detection
# ---------------------------------------------------------------------------

def _is_msgspec_struct(schema: object) -> bool:
    return isinstance(schema, type) and issubclass(schema, msgspec.Struct)


def _is_dataclass(schema: object) -> bool:
    return isinstance(schema, type) and dataclasses.is_dataclass(schema)


# ---------------------------------------------------------------------------
# Core extraction (schema-agnostic)
# ---------------------------------------------------------------------------

def _run_pipeline(text: str) -> tuple[object, bool, int, str, tuple[str, ...]]:
    """Runs preprocess → repair and returns resolved payload plus repair metadata.

    Returns:
        Tuple of (payload, repair_applied, repair_attempts, repaired_text, strategy_trace).
    """
    preprocessed = preprocess(text)
    repair_result = repair(preprocessed)
    payload = _resolve_payload(repair_result.repaired_text, repair_result.data)
    return (
        payload,
        repair_result.repair_applied,
        repair_result.repair_attempts,
        repair_result.repaired_text,
        repair_result.strategy_trace,
    )


def _validate(data: object, schema: type[T]) -> T:
    """Routes validation to the correct adapter based on schema type."""
    if _is_msgspec_struct(schema):
        return validate_with_msgspec(data, schema)  # type: ignore[arg-type]
    if is_pydantic_model(schema):
        return validate_with_pydantic(data, schema)
    if _is_dataclass(schema):
        # msgspec.convert supports dataclasses natively
        try:
            return msgspec.convert(data, type=schema, strict=False)  # type: ignore[type-var]
        except (msgspec.ValidationError, TypeError) as exc:
            msg = f"{schema.__name__} dataclass validation failed: {exc}"
            raise TypeError(msg) from exc
    msg = (
        f"Unsupported schema type {schema!r}. "
        "Use a msgspec.Struct, pydantic.BaseModel, or dataclass."
    )
    raise TypeError(msg)


def _resolve_payload(repaired_text: str, parsed_data: object | None) -> object:
    """Picks the validation payload without redundant re-parsing on hot paths."""
    if parsed_data is not None:
        return parsed_data

    reparsed, success = try_orjson_parse(repaired_text)
    if success:
        return reparsed
    return repaired_text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract(text: str, schema: type[T]) -> ExtractionResult[T]:
    """Extracts a typed instance from raw JSON-like text.

    Handles msgspec Structs, Pydantic v2 BaseModel subclasses, and standard
    Python dataclasses. Automatically preprocesses markdown fences, repairs
    malformed JSON (trailing commas, single quotes, bare keys, Python literals,
    C-style comments, JSON embedded in prose), and returns a confidence score
    alongside the validated result.

    Args:
        text: Raw input text to preprocess, repair, and validate. May be model
            output, OCR text, or any other JSON-like string.
        schema: Target schema type. Supports ``msgspec.Struct``,
            ``pydantic.BaseModel``, and ``dataclasses.dataclass``.

    Returns:
        An ``ExtractionResult`` containing the validated data, repair metadata,
        latency, and a confidence score.

    Raises:
        MsgspecValidationError: If a msgspec schema cannot be satisfied.
        PydanticValidationError: If a Pydantic schema cannot be satisfied.
        TypeError: If the schema type is unsupported or validation fails.
    """
    start = time.perf_counter()
    payload, repair_applied, repair_attempts, repaired_text, strategy_trace = _run_pipeline(text)
    validated = _validate(payload, schema)
    latency_ms = (time.perf_counter() - start) * 1000.0
    confidence = compute_confidence(repair_applied, strategy_trace)

    return ExtractionResult(
        data=validated,
        repair_applied=repair_applied,
        repair_attempts=repair_attempts,
        raw_input=text,
        repaired_text=repaired_text,
        latency_ms=latency_ms,
        confidence=confidence,
        strategy_trace=strategy_trace,
    )


def extract_list(
    text: str, schema: type[T], *, max_items: int | None = None
) -> ExtractionResult[list[T]]:
    """Extracts a typed list of instances from a JSON array in raw text.

    Args:
        text: Raw input text containing a JSON array of objects.
        schema: Target item schema type. Supports the same types as
            :func:`extract`.
        max_items: When provided, silently truncates the list to this many
            items after validation.

    Returns:
        An ``ExtractionResult`` whose ``data`` field is a ``list[schema]``.

    Raises:
        MsgspecValidationError: If a msgspec schema cannot be satisfied.
        PydanticValidationError: If a Pydantic schema cannot be satisfied.
        TypeError: If the schema type is unsupported or the payload is not a list.
    """
    start = time.perf_counter()
    payload, repair_applied, repair_attempts, repaired_text, strategy_trace = _run_pipeline(text)

    if not isinstance(payload, list):
        msg = (
            f"extract_list expected a JSON array but got {type(payload).__name__!r}. "
            "Check that the input text contains a top-level JSON array."
        )
        raise TypeError(msg)

    if _is_msgspec_struct(schema):
        validated_list: list[T] = [validate_with_msgspec(item, schema) for item in payload]  # type: ignore[arg-type]
    elif is_pydantic_model(schema):
        validated_list = [validate_with_pydantic(item, schema) for item in payload]
    else:
        try:
            validated_list = [
                msgspec.convert(item, type=schema, strict=False)  # type: ignore[type-var]
                for item in payload
            ]
        except (msgspec.ValidationError, TypeError) as exc:
            msg = f"List item validation failed for {schema.__name__}: {exc}"
            raise TypeError(msg) from exc

    if max_items is not None:
        validated_list = validated_list[:max_items]

    latency_ms = (time.perf_counter() - start) * 1000.0
    confidence = compute_confidence(repair_applied, strategy_trace)

    return ExtractionResult(
        data=validated_list,
        repair_applied=repair_applied,
        repair_attempts=repair_attempts,
        raw_input=text,
        repaired_text=repaired_text,
        latency_ms=latency_ms,
        confidence=confidence,
        strategy_trace=strategy_trace,
    )


async def extract_async(text: str, schema: type[T]) -> ExtractionResult[T]:
    """Async variant of :func:`extract` that runs the pipeline in a thread pool.

    Safe to ``await`` from any asyncio coroutine. Does not block the event loop.

    Args:
        text: Raw input text. Same semantics as :func:`extract`.
        schema: Target schema type. Same semantics as :func:`extract`.

    Returns:
        Same ``ExtractionResult`` as :func:`extract`.
    """
    import asyncio

    return await asyncio.to_thread(extract, text, schema)


async def extract_list_async(
    text: str,
    schema: type[T],
    *,
    max_items: int | None = None,
) -> ExtractionResult[list[T]]:
    """Async variant of :func:`extract_list`.

    Args:
        text: Raw input text containing a JSON array.
        schema: Target item schema type.
        max_items: Optional upper bound on list length after validation.

    Returns:
        Same ``ExtractionResult`` as :func:`extract_list`.
    """
    import asyncio
    import functools

    fn = functools.partial(extract_list, max_items=max_items)
    return await asyncio.to_thread(fn, text, schema)
