"""Unit tests for the minimal sync extraction pipeline."""

from __future__ import annotations

import msgspec
import pytest

from confident_extract.core.extractor import extract
from confident_extract.core.result import ExtractionResult
from confident_extract.validators.msgspec_adapter import MsgspecValidationError


class Contact(msgspec.Struct):
    """Nested contact schema fixture."""

    email: str
    phone: str | None = None


class Customer(msgspec.Struct):
    """Nested customer schema fixture."""

    name: str
    contact: Contact


class LineItem(msgspec.Struct):
    """Line-item schema fixture."""

    sku: str
    quantity: int


class Invoice(msgspec.Struct):
    """Invoice schema fixture."""

    invoice_id: int
    customer: Customer
    line_items: list[LineItem]
    totals: dict[str, int]
    note: str | None = None


def test_extract_successful_path_returns_extraction_result() -> None:
    """Valid clean JSON extracts into a typed result."""
    text = (
        '{"invoice_id": 42, "customer": {"name": "Acme", '
        '"contact": {"email": "ops@example.com"}}, '
        '"line_items": [{"sku": "SKU-1", "quantity": 2}], '
        '"totals": {"subtotal": 20}}'
    )

    result = extract(text, Invoice)

    assert isinstance(result, ExtractionResult)
    assert isinstance(result.data, Invoice)
    assert result.data.invoice_id == 42
    assert result.data.customer.contact.email == "ops@example.com"
    assert result.repair_applied is False
    assert result.repair_attempts == 0


def test_extract_repairs_malformed_json_successfully() -> None:
    """Preprocesses and repairs a malformed JSON-like payload before validation."""
    text = (
        " \n```json\n"
        "{invoice_id: 42, customer: {name: 'Acme', contact: {email: 'ops@example.com'}}, "
        "line_items: [{sku: 'SKU-1', quantity: 2}], totals: {subtotal: 20},}\n"
        "```\n"
    )

    result = extract(text, Invoice)

    assert result.data == Invoice(
        invoice_id=42,
        customer=Customer(name="Acme", contact=Contact(email="ops@example.com")),
        line_items=[LineItem(sku="SKU-1", quantity=2)],
        totals={"subtotal": 20},
    )
    assert result.repair_applied is True
    assert result.repair_attempts == 3
    assert result.raw_input == text
    assert result.repaired_text == (
        '{"invoice_id": 42, "customer": {"name": "Acme", '
        '"contact": {"email": "ops@example.com"}}, '
        '"line_items": [{"sku": "SKU-1", "quantity": 2}], '
        '"totals": {"subtotal": 20}}'
    )


def test_extract_propagates_validation_failures_cleanly() -> None:
    """Raises the msgspec validation adapter error without wrapping it again."""
    text = (
        '{"invoice_id": 42, "customer": {"name": "Acme", '
        '"contact": {"email": 123}}, "line_items": [], "totals": {}}'
    )

    with pytest.raises(MsgspecValidationError) as exc_info:
        extract(text, Invoice)

    error = exc_info.value.validation_errors[0]
    assert error.field_path == ("customer", "contact", "email")
    assert error.raw_error == "Expected `str`, got `int` - at `$.customer.contact.email`"


def test_extract_already_valid_fast_path_preserves_clean_payload() -> None:
    """Keeps already-valid JSON on the hot path with no repair metadata."""
    text = (
        '{"invoice_id": 7, "customer": {"name": "Acme", '
        '"contact": {"email": "ops@example.com"}}, "line_items": [], "totals": {}}'
    )

    result = extract(text, Invoice)

    assert result.repair_applied is False
    assert result.repair_attempts == 0
    assert result.repaired_text == text


def test_extract_populates_latency_field() -> None:
    """Sets a non-negative wall-clock latency on success."""
    result = extract(
        '{"invoice_id": 1, "customer": {"name": "Acme", '
        '"contact": {"email": "ops@example.com"}}, "line_items": [], "totals": {}}',
        Invoice,
    )

    assert isinstance(result.latency_ms, float)
    assert result.latency_ms >= 0.0


def test_extract_preserves_raw_input_verbatim() -> None:
    """Retains the original caller input even when preprocessing changes it."""
    text = (
        ' \r\n```json\r\n{"invoice_id": 1, "customer": {"name": "Acme", '
        '"contact": {"email": "ops@example.com"}}, "line_items": [], '
        '"totals": {}}\r\n```\r\n'
    )

    result = extract(text, Invoice)

    assert result.raw_input == text
    assert result.repaired_text == (
        '{"invoice_id": 1, "customer": {"name": "Acme", '
        '"contact": {"email": "ops@example.com"}}, "line_items": [], "totals": {}}'
    )


def test_extract_returns_nested_schema_instances() -> None:
    """Builds nested msgspec.Struct instances through the full pipeline."""
    result = extract(
        '{"invoice_id": 10, "customer": {"name": "Globex", '
        '"contact": {"email": "billing@example.com", "phone": "123"}}, '
        '"line_items": [{"sku": "A", "quantity": 1}, {"sku": "B", "quantity": 2}], '
        '"totals": {"subtotal": 30}}',
        Invoice,
    )

    assert isinstance(result.data.customer, Customer)
    assert isinstance(result.data.customer.contact, Contact)
    assert isinstance(result.data.line_items[0], LineItem)
    assert result.data.customer.contact.phone == "123"


def test_extract_empty_input_fails_validation() -> None:
    """Empty input fails cleanly once the pipeline reaches validation."""
    with pytest.raises(MsgspecValidationError) as exc_info:
        extract("", Invoice)

    assert exc_info.value.validation_errors[0].field_path == ()


def test_extract_is_idempotent_on_repaired_output() -> None:
    """Rerunning extraction on repaired output produces the same typed data."""
    first = extract(
        "{invoice_id: 42, customer: {name: 'Acme', contact: {email: 'ops@example.com'}}, "
        "line_items: [{sku: 'SKU-1', quantity: 2}], totals: {subtotal: 20},}",
        Invoice,
    )
    second = extract(first.repaired_text, Invoice)

    assert first.data == second.data
    assert second.repair_applied is False
    assert second.repair_attempts == 0
    assert second.repaired_text == first.repaired_text
