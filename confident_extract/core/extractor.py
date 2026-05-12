"""Minimal synchronous extraction pipeline."""

from __future__ import annotations

import time
from typing import TypeVar

import msgspec

from confident_extract.core.preprocessor import preprocess
from confident_extract.core.result import ExtractionResult
from confident_extract.repair.engine import repair
from confident_extract.repair.strategies import try_orjson_parse
from confident_extract.validators.msgspec_adapter import validate_with_msgspec

T = TypeVar("T", bound=msgspec.Struct)


def extract(text: str, schema: type[T]) -> ExtractionResult[T]:
    """Extracts a typed schema instance from raw JSON-like text.

    Args:
        text: Raw input text to preprocess, repair, and validate.
        schema: Target `msgspec.Struct` schema type.

    Returns:
        A lightweight extraction result containing the validated data and
        repair metadata.

    Raises:
        MsgspecValidationError: If the final payload cannot be validated
            against the provided schema.
        TypeError: If the schema type is unsupported.
    """
    start = time.perf_counter()
    preprocessed_text = preprocess(text)
    repair_result = repair(preprocessed_text)
    payload = _resolve_payload(repair_result.repaired_text, repair_result.data)
    validated = validate_with_msgspec(payload, schema)
    latency_ms = (time.perf_counter() - start) * 1000.0

    return ExtractionResult(
        data=validated,
        repair_applied=repair_result.repair_applied,
        repair_attempts=repair_result.repair_attempts,
        raw_input=text,
        repaired_text=repair_result.repaired_text,
        latency_ms=latency_ms,
    )


def _resolve_payload(repaired_text: str, parsed_data: object | None) -> object:
    """Chooses the validation payload without reparsing successful hot paths."""
    if parsed_data is not None:
        return parsed_data

    reparsed_data, success = try_orjson_parse(repaired_text)
    if success:
        return reparsed_data
    return repaired_text
