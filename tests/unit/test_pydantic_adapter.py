"""Tests for the Pydantic v2 validation adapter."""

from __future__ import annotations

import pytest

pydantic = pytest.importorskip("pydantic", reason="pydantic not installed")

from pydantic import BaseModel  # noqa: E402

from confident_extract import extract  # noqa: E402
from confident_extract.validators.pydantic_adapter import (  # noqa: E402
    PydanticValidationError,
    is_pydantic_model,
    validate_with_pydantic,
)


class Address(BaseModel):
    street: str
    city: str
    zip_code: str | None = None


class Order(BaseModel):
    order_id: int
    status: str
    address: Address
    tags: list[str] = []


class TestIsPydanticModel:
    def test_base_model_subclass(self) -> None:
        assert is_pydantic_model(Order) is True

    def test_non_model_returns_false(self) -> None:
        assert is_pydantic_model(dict) is False
        assert is_pydantic_model(str) is False

    def test_instance_returns_false(self) -> None:
        instance = Order(order_id=1, status="ok", address=Address(street="Main", city="NYC"))
        assert is_pydantic_model(instance) is False


class TestValidateWithPydantic:
    def test_valid_dict_round_trips(self) -> None:
        data = {
            "order_id": 7,
            "status": "shipped",
            "address": {"street": "1 Main St", "city": "Boston"},
        }
        result = validate_with_pydantic(data, Order)
        assert result.order_id == 7
        assert result.address.city == "Boston"

    def test_invalid_data_raises(self) -> None:
        with pytest.raises(PydanticValidationError) as exc_info:
            validate_with_pydantic({"order_id": "not-an-int"}, Order)
        assert exc_info.value.validation_errors

    def test_non_model_schema_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            validate_with_pydantic({}, dict)  # type: ignore[arg-type]


class TestExtractWithPydanticSchema:
    def test_valid_json_with_pydantic_schema(self) -> None:
        raw = '{"order_id": 42, "status": "paid", "address": {"street": "2nd Ave", "city": "NY"}}'
        result = extract(raw, Order)
        assert result.data.order_id == 42
        assert result.data.address.city == "NY"
        assert result.confidence.score == 1.0

    def test_malformed_json_with_pydantic_schema(self) -> None:
        raw = "{order_id: 99, status: 'pending', address: {street: '3rd St', city: 'LA'}}"
        result = extract(raw, Order)
        assert result.data.order_id == 99
        assert result.repair_applied is True
        assert result.confidence.score < 1.0

    def test_python_literals_in_pydantic_schema(self) -> None:
        addr = '{"street": "A", "city": "B"}'
        raw = f'{{"order_id": 1, "status": "ok", "address": {addr}, "tags": []}}'
        result = extract(raw, Order)
        assert result.data.tags == []

    def test_prose_wrapping_with_pydantic_schema(self) -> None:
        addr = '{"street": "X", "city": "Z"}'
        raw = f'Here is your order: {{"order_id": 5, "status": "done", "address": {addr}}}'
        result = extract(raw, Order)
        assert result.data.order_id == 5
        assert result.repair_applied is True
