"""Unit tests for the msgspec validation adapter."""

from __future__ import annotations

from typing import cast

import msgspec
import pytest

from confident_extract.validators.msgspec_adapter import (
    MsgspecValidationError,
    ValidationError,
    validate_with_msgspec,
)


class LineItem(msgspec.Struct):
    """Line-item fixture schema for validation tests."""

    sku: str
    quantity: int


class Address(msgspec.Struct):
    """Address fixture schema for validation tests."""

    city: str
    zip_code: int


class Invoice(msgspec.Struct):
    """Invoice fixture schema for validation tests."""

    invoice_id: int
    customer_name: str
    shipping_address: Address
    line_items: list[LineItem]
    totals: dict[str, int]
    note: str | None = None


def test_validation_error_dataclass_fields() -> None:
    """Exposes the documented validation error fields."""
    error = ValidationError(
        message="Expected `int`, got `str`",
        field_path=("invoice_id",),
        raw_error="Expected `int`, got `str` - at `$.invoice_id`",
    )

    assert error.message == "Expected `int`, got `str`"
    assert error.field_path == ("invoice_id",)
    assert error.raw_error == "Expected `int`, got `str` - at `$.invoice_id`"


def test_validate_with_msgspec_returns_typed_schema_instance() -> None:
    """Validates decoded Python data into a strongly typed schema."""
    data = {
        "invoice_id": 42,
        "customer_name": "Acme",
        "shipping_address": {"city": "Sydney", "zip_code": 2000},
        "line_items": [{"sku": "SKU-1", "quantity": 2}],
        "totals": {"subtotal": 20},
    }

    result = validate_with_msgspec(data, Invoice)

    assert isinstance(result, Invoice)
    assert result.invoice_id == 42
    assert isinstance(result.shipping_address, Address)
    assert isinstance(result.line_items[0], LineItem)


def test_validate_with_msgspec_returns_existing_instance_via_fast_path() -> None:
    """Returns the same object when data is already a validated schema instance."""
    invoice = Invoice(
        invoice_id=7,
        customer_name="Acme",
        shipping_address=Address(city="Melbourne", zip_code=3000),
        line_items=[LineItem(sku="SKU-1", quantity=1)],
        totals={"subtotal": 10},
    )

    result = validate_with_msgspec(invoice, Invoice)

    assert result is invoice


def test_validate_with_msgspec_supports_nested_structs() -> None:
    """Validates nested msgspec.Struct fields."""
    result = validate_with_msgspec(
        {
            "invoice_id": 1,
            "customer_name": "Acme",
            "shipping_address": {"city": "Perth", "zip_code": 6000},
            "line_items": [{"sku": "SKU-1", "quantity": 3}],
            "totals": {"subtotal": 30},
        },
        Invoice,
    )

    assert result.shipping_address.city == "Perth"
    assert result.line_items[0].quantity == 3


def test_validate_with_msgspec_supports_optional_fields() -> None:
    """Allows missing optional fields and preserves explicit null values."""
    missing_optional = validate_with_msgspec(
        {
            "invoice_id": 1,
            "customer_name": "Acme",
            "shipping_address": {"city": "Perth", "zip_code": 6000},
            "line_items": [],
            "totals": {},
        },
        Invoice,
    )
    explicit_none = validate_with_msgspec(
        {
            "invoice_id": 1,
            "customer_name": "Acme",
            "shipping_address": {"city": "Perth", "zip_code": 6000},
            "line_items": [],
            "totals": {},
            "note": None,
        },
        Invoice,
    )

    assert missing_optional.note is None
    assert explicit_none.note is None


def test_validate_with_msgspec_enforces_missing_required_field() -> None:
    """Surfaces missing top-level required field information."""
    with pytest.raises(MsgspecValidationError) as exc_info:
        validate_with_msgspec(
            {
                "customer_name": "Acme",
                "shipping_address": {"city": "Perth", "zip_code": 6000},
                "line_items": [],
                "totals": {},
            },
            Invoice,
        )

    error = exc_info.value.validation_errors[0]
    assert error.message == "Object missing required field `invoice_id`"
    assert error.field_path == ("invoice_id",)
    assert error.raw_error == "Object missing required field `invoice_id`"
    assert "Invoice validation failed at invoice_id" in exc_info.value.summary
    assert isinstance(exc_info.value.__cause__, msgspec.ValidationError)


def test_validate_with_msgspec_enforces_strict_field_types() -> None:
    """Does not coerce incompatible types."""
    with pytest.raises(MsgspecValidationError) as exc_info:
        validate_with_msgspec(
            {
                "invoice_id": "42",
                "customer_name": "Acme",
                "shipping_address": {"city": "Perth", "zip_code": 6000},
                "line_items": [],
                "totals": {},
            },
            Invoice,
        )

    error = exc_info.value.validation_errors[0]
    assert error.message == "Expected `int`, got `str`"
    assert error.field_path == ("invoice_id",)
    assert error.raw_error == "Expected `int`, got `str` - at `$.invoice_id`"


def test_validate_with_msgspec_surfaces_nested_missing_field_path() -> None:
    """Appends the missing nested field name to the parent path."""
    with pytest.raises(MsgspecValidationError) as exc_info:
        validate_with_msgspec(
            {
                "invoice_id": 42,
                "customer_name": "Acme",
                "shipping_address": {"zip_code": 6000},
                "line_items": [],
                "totals": {},
            },
            Invoice,
        )

    error = exc_info.value.validation_errors[0]
    assert error.message == "Object missing required field `city`"
    assert error.field_path == ("shipping_address", "city")
    assert error.raw_error == "Object missing required field `city` - at `$.shipping_address`"
    assert "shipping_address.city" in exc_info.value.summary


def test_validate_with_msgspec_surfaces_nested_invalid_type_path() -> None:
    """Extracts dotted nested field paths on type failures."""
    with pytest.raises(MsgspecValidationError) as exc_info:
        validate_with_msgspec(
            {
                "invoice_id": 42,
                "customer_name": "Acme",
                "shipping_address": {"city": 123, "zip_code": 6000},
                "line_items": [],
                "totals": {},
            },
            Invoice,
        )

    error = exc_info.value.validation_errors[0]
    assert error.message == "Expected `str`, got `int`"
    assert error.field_path == ("shipping_address", "city")
    assert error.raw_error == "Expected `str`, got `int` - at `$.shipping_address.city`"


def test_validate_with_msgspec_surfaces_list_index_paths() -> None:
    """Captures nested array indices in the field path."""
    with pytest.raises(MsgspecValidationError) as exc_info:
        validate_with_msgspec(
            {
                "invoice_id": 42,
                "customer_name": "Acme",
                "shipping_address": {"city": "Perth", "zip_code": 6000},
                "line_items": [{"sku": "SKU-1", "quantity": "two"}],
                "totals": {},
            },
            Invoice,
        )

    error = exc_info.value.validation_errors[0]
    assert error.message == "Expected `int`, got `str`"
    assert error.field_path == ("line_items", "0", "quantity")
    assert error.raw_error == "Expected `int`, got `str` - at `$.line_items[0].quantity`"


def test_validate_with_msgspec_surfaces_dict_value_paths() -> None:
    """Captures dict-value placeholder paths from msgspec."""
    with pytest.raises(MsgspecValidationError) as exc_info:
        validate_with_msgspec(
            {
                "invoice_id": 42,
                "customer_name": "Acme",
                "shipping_address": {"city": "Perth", "zip_code": 6000},
                "line_items": [],
                "totals": {"subtotal": "20"},
            },
            Invoice,
        )

    error = exc_info.value.validation_errors[0]
    assert error.message == "Expected `int`, got `str`"
    assert error.field_path == ("totals", "...")
    assert error.raw_error == "Expected `int`, got `str` - at `$.totals[...]`"
    assert "totals[...]" in exc_info.value.summary


def test_validate_with_msgspec_handles_invalid_root_structure() -> None:
    """Reports root-level structure mismatches without a field path."""
    with pytest.raises(MsgspecValidationError) as exc_info:
        validate_with_msgspec([], Invoice)

    error = exc_info.value.validation_errors[0]
    assert error.message == "Expected `object`, got `array`"
    assert error.field_path == ()
    assert error.raw_error == "Expected `object`, got `array`"
    assert exc_info.value.summary == "Invoice validation failed: Expected `object`, got `array`"


def test_validate_with_msgspec_handles_empty_payload() -> None:
    """Treats an empty payload as missing required fields."""
    with pytest.raises(MsgspecValidationError) as exc_info:
        validate_with_msgspec({}, Invoice)

    error = exc_info.value.validation_errors[0]
    assert error.field_path == ("invoice_id",)


def test_validate_with_msgspec_rejects_non_msgspec_schema() -> None:
    """Raises a clear type error for unsupported schema classes."""

    class NotAStruct:
        pass

    with pytest.raises(TypeError) as exc_info:
        validate_with_msgspec({}, cast("type[msgspec.Struct]", NotAStruct))

    assert "msgspec.Struct subclass" in str(exc_info.value)
