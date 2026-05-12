"""Extraction result contract for the sync pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

import msgspec

T = TypeVar("T", bound=msgspec.Struct)


@dataclass(frozen=True, slots=True)
class ExtractionResult(Generic[T]):
    """Result returned by the sync extraction pipeline.

    Attributes:
        data: Strongly typed validated schema instance.
        repair_applied: Whether JSON repair mutated the payload.
        repair_attempts: Number of repair mutations attempted.
        raw_input: Original caller-provided input text.
        repaired_text: Final pre-validation JSON text after repair.
        latency_ms: End-to-end wall-clock latency in milliseconds.
    """

    data: T
    repair_applied: bool
    repair_attempts: int
    raw_input: str
    repaired_text: str
    latency_ms: float
