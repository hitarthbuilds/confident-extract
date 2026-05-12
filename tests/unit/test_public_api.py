"""Package-root smoke tests for the public API surface."""

from __future__ import annotations

import subprocess
import sys

import msgspec

import confident_extract
from confident_extract import (
    ExtractionResult,
    MsgspecValidationError,
    ValidationError,
    extract,
)


class Contact(msgspec.Struct):
    """Nested contact schema fixture for public API tests."""

    email: str
    phone: str | None = None


class Customer(msgspec.Struct):
    """Nested customer schema fixture for public API tests."""

    name: str
    contact: Contact


class Invoice(msgspec.Struct):
    """Invoice schema fixture for public API tests."""

    invoice_id: int
    customer: Customer
    tags: list[str]


def test_package_root_import_exposes_expected_symbols() -> None:
    """Package root imports expose the supported public API."""
    assert callable(confident_extract.extract)
    assert confident_extract.extract is extract
    assert confident_extract.ExtractionResult is ExtractionResult
    assert confident_extract.MsgspecValidationError is MsgspecValidationError
    assert confident_extract.ValidationError is ValidationError
    assert confident_extract.__all__ == [
        "ExtractionResult",
        "MsgspecValidationError",
        "ValidationError",
        "__version__",
        "extract",
    ]


def test_extract_import_works_cleanly() -> None:
    """The sync extract function imports from the package root."""
    assert callable(extract)


def test_extraction_result_import_works_cleanly() -> None:
    """The extraction result type imports from the package root."""
    assert ExtractionResult.__name__ == "ExtractionResult"


def test_validation_error_imports_work_cleanly() -> None:
    """The validation error types import from the package root."""
    assert MsgspecValidationError.__name__ == "MsgspecValidationError"
    assert ValidationError.__name__ == "ValidationError"


def test_minimal_successful_extraction_example() -> None:
    """A simple package-root extraction call succeeds."""
    result = extract(
        '{"invoice_id": 1, "customer": {"name": "Acme", '
        '"contact": {"email": "ops@example.com"}}, "tags": ["paid"]}',
        Invoice,
    )

    assert isinstance(result, ExtractionResult)
    assert result.data == Invoice(
        invoice_id=1,
        customer=Customer(name="Acme", contact=Contact(email="ops@example.com")),
        tags=["paid"],
    )


def test_nested_schema_extraction_example() -> None:
    """Nested msgspec schemas work through the package-root API."""
    result = extract(
        "{invoice_id: 2, customer: {name: 'Globex', "
        "contact: {email: 'billing@example.com', phone: '123'}}, "
        "tags: ['vip', 'net30']}",
        Invoice,
    )

    assert result.data.customer == Customer(
        name="Globex",
        contact=Contact(email="billing@example.com", phone="123"),
    )
    assert result.data.tags == ["vip", "net30"]


def test_package_root_import_has_no_provider_side_effects() -> None:
    """Importing the package root avoids provider imports and side effects."""
    command = [
        sys.executable,
        "-c",
        (
            "import confident_extract, sys; "
            "assert 'confident_extract.providers' not in sys.modules; "
            "assert 'openai' not in sys.modules; "
            "assert 'anthropic' not in sys.modules; "
            "assert 'pydantic' not in sys.modules"
        ),
    ]

    completed = subprocess.run(command, check=False, capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
