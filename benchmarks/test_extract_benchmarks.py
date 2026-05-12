"""Initial benchmark suite for the current synchronous extraction hot path."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, TypeVar

import msgspec
import orjson
import pytest

from confident_extract.core.extractor import extract
from confident_extract.core.preprocessor import preprocess
from confident_extract.repair.engine import RepairResult, repair
from confident_extract.validators.msgspec_adapter import validate_with_msgspec

if TYPE_CHECKING:
    from collections.abc import Callable


class Contact(msgspec.Struct):
    """Nested contact schema fixture for benchmarks."""

    email: str
    phone: str | None = None


class Customer(msgspec.Struct):
    """Nested customer schema fixture for benchmarks."""

    name: str
    contact: Contact
    region: str


class LineItem(msgspec.Struct):
    """Line-item schema fixture for benchmarks."""

    sku: str
    quantity: int
    attributes: dict[str, str]


class Invoice(msgspec.Struct):
    """Invoice schema fixture for benchmarks."""

    invoice_id: int
    customer: Customer
    line_items: list[LineItem]
    totals: dict[str, int]
    tags: list[str]
    note: str | None = None


R = TypeVar("R")


class _BenchmarkFixture(Protocol):
    """Minimal protocol for the pytest-benchmark fixture methods used here."""

    def __call__(self, function: Callable[..., R], /, *args: object, **kwargs: object) -> R:
        """Runs a benchmarked callable and returns its final result."""

    def pedantic(
        self,
        function: Callable[..., R],
        /,
        *,
        args: tuple[object, ...] = (),
        kwargs: dict[str, object] | None = None,
        iterations: int,
        rounds: int,
    ) -> R:
        """Runs a benchmark with explicit iteration and round control."""


def _build_small_payload() -> dict[str, object]:
    return {
        "invoice_id": 42,
        "customer": {
            "name": "Acme",
            "contact": {"email": "ops@example.com", "phone": "123"},
            "region": "apac",
        },
        "line_items": [
            {"sku": "SKU-1", "quantity": 2, "attributes": {"category": "core"}},
            {"sku": "SKU-2", "quantity": 1, "attributes": {"category": "addon"}},
        ],
        "totals": {"subtotal": 30, "tax": 3, "grand_total": 33},
        "tags": ["paid", "net30"],
        "note": "deliver before friday",
    }


def _build_large_payload() -> dict[str, object]:
    line_items = [
        {
            "sku": f"SKU-{index:03d}",
            "quantity": (index % 5) + 1,
            "attributes": {
                "category": "core" if index % 2 == 0 else "addon",
                "warehouse": f"WH-{index % 7}",
                "batch": f"BATCH-{index:04d}",
            },
        }
        for index in range(72)
    ]
    return {
        "invoice_id": 9001,
        "customer": {
            "name": "Example Industries",
            "contact": {"email": "billing@example.com", "phone": "+61-555-0100"},
            "region": "global",
        },
        "line_items": line_items,
        "totals": {"subtotal": 18420, "tax": 1842, "grand_total": 20262},
        "tags": ["priority", "quarter-close", "benchmark"],
        "note": "x" * 3200,
    }


SMALL_PAYLOAD: Final[dict[str, object]] = _build_small_payload()
SMALL_VALID_JSON: Final[str] = orjson.dumps(SMALL_PAYLOAD).decode("utf-8")
SMALL_TRAILING_COMMA_JSON: Final[str] = (
    '{"invoice_id": 42, "customer": {"name": "Acme", '
    '"contact": {"email": "ops@example.com", "phone": "123"}, "region": "apac"}, '
    '"line_items": [{"sku": "SKU-1", "quantity": 2, "attributes": {"category": "core"}}, '
    '{"sku": "SKU-2", "quantity": 1, "attributes": {"category": "addon"}},], '
    '"totals": {"subtotal": 30, "tax": 3, "grand_total": 33}, '
    '"tags": ["paid", "net30"], "note": "deliver before friday",}'
)
SMALL_MULTI_REPAIR_JSON: Final[str] = (
    "{invoice_id: 42, customer: {name: 'Acme', contact: {email: 'ops@example.com', "
    "phone: '123'}, region: 'apac'}, line_items: [{sku: 'SKU-1', quantity: 2, "
    "attributes: {category: 'core'}}, {sku: 'SKU-2', quantity: 1, attributes: "
    "{category: 'addon'}}], totals: {subtotal: 30, tax: 3, grand_total: 33}, "
    "tags: ['paid', 'net30'], note: 'deliver before friday'}"
)
SMALL_FENCED_JSON: Final[str] = f"```json\n{SMALL_VALID_JSON}\n```"

LARGE_PAYLOAD: Final[dict[str, object]] = _build_large_payload()
LARGE_VALID_JSON: Final[str] = orjson.dumps(LARGE_PAYLOAD).decode("utf-8")
LARGE_FENCED_JSON: Final[str] = f"```json\n{LARGE_VALID_JSON}\n```"
LARGE_SCHEMA_INSTANCE: Final[Invoice] = validate_with_msgspec(LARGE_PAYLOAD, Invoice)

assert len(LARGE_VALID_JSON.encode("utf-8")) >= 10_000


@pytest.mark.benchmark(group="preprocess")
def test_benchmark_preprocess_valid_fast_path(benchmark: _BenchmarkFixture) -> None:
    """Benchmarks the already-valid preprocess hot path."""
    result = benchmark(preprocess, SMALL_VALID_JSON)

    assert result == SMALL_VALID_JSON


@pytest.mark.benchmark(group="preprocess")
def test_benchmark_preprocess_large_fenced_payload(benchmark: _BenchmarkFixture) -> None:
    """Benchmarks preprocessing a fenced payload around 10KB."""
    result = benchmark(preprocess, LARGE_FENCED_JSON)

    assert result == LARGE_VALID_JSON


@pytest.mark.benchmark(group="repair")
def test_benchmark_repair_valid_fast_path(benchmark: _BenchmarkFixture) -> None:
    """Benchmarks repair on already-valid JSON."""
    result = benchmark(repair, SMALL_VALID_JSON)

    assert isinstance(result, RepairResult)
    assert result.repair_applied is False
    assert result.repair_attempts == 0


@pytest.mark.benchmark(group="repair")
def test_benchmark_repair_trailing_comma_path(benchmark: _BenchmarkFixture) -> None:
    """Benchmarks repair on a payload requiring trailing-comma cleanup."""
    result = benchmark(repair, SMALL_TRAILING_COMMA_JSON)

    assert result.repair_applied is True
    assert result.repair_attempts == 1


@pytest.mark.benchmark(group="repair")
def test_benchmark_repair_multi_strategy_path(benchmark: _BenchmarkFixture) -> None:
    """Benchmarks repair on a payload requiring multiple mutations."""
    result = benchmark(repair, SMALL_MULTI_REPAIR_JSON)

    assert result.repair_applied is True
    assert result.repair_attempts == 2


@pytest.mark.benchmark(group="validate")
def test_benchmark_validate_nested_payload(benchmark: _BenchmarkFixture) -> None:
    """Benchmarks msgspec validation for a nested decoded payload."""
    result = benchmark(validate_with_msgspec, SMALL_PAYLOAD, Invoice)

    assert isinstance(result, Invoice)
    assert result.customer.contact.email == "ops@example.com"


@pytest.mark.benchmark(group="validate")
def test_benchmark_validate_large_decoded_payload(benchmark: _BenchmarkFixture) -> None:
    """Benchmarks msgspec validation for a decoded payload around 10KB."""
    result = benchmark(validate_with_msgspec, LARGE_PAYLOAD, Invoice)

    assert isinstance(result, Invoice)
    assert len(result.line_items) == 72


@pytest.mark.benchmark(group="validate")
def test_benchmark_validate_existing_instance_fast_path(
    benchmark: _BenchmarkFixture,
) -> None:
    """Benchmarks the schema-instance fast path for validation."""
    result = benchmark(validate_with_msgspec, LARGE_SCHEMA_INSTANCE, Invoice)

    assert result is LARGE_SCHEMA_INSTANCE


@pytest.mark.benchmark(group="extract")
def test_benchmark_extract_valid_fast_path(benchmark: _BenchmarkFixture) -> None:
    """Benchmarks full extraction for already-valid JSON."""
    result = benchmark(extract, SMALL_VALID_JSON, Invoice)

    assert result.repair_applied is False
    assert result.data.invoice_id == 42


@pytest.mark.benchmark(group="extract")
def test_benchmark_extract_trailing_comma_path(benchmark: _BenchmarkFixture) -> None:
    """Benchmarks full extraction when trailing-comma repair is needed."""
    result = benchmark(extract, SMALL_TRAILING_COMMA_JSON, Invoice)

    assert result.repair_applied is True
    assert result.repair_attempts == 1


@pytest.mark.benchmark(group="extract")
def test_benchmark_extract_multi_strategy_nested_path(
    benchmark: _BenchmarkFixture,
) -> None:
    """Benchmarks full extraction when multiple repair strategies are needed."""
    result = benchmark(extract, SMALL_MULTI_REPAIR_JSON, Invoice)

    assert result.repair_applied is True
    assert result.repair_attempts == 2
    assert result.data.customer.contact.phone == "123"


@pytest.mark.benchmark(group="extract")
def test_benchmark_extract_large_nested_payload(benchmark: _BenchmarkFixture) -> None:
    """Benchmarks full extraction for a nested payload around 10KB."""
    result = benchmark(extract, LARGE_VALID_JSON, Invoice)

    assert result.repair_applied is False
    assert len(result.data.line_items) == 72


@pytest.mark.benchmark(group="throughput")
def test_benchmark_extract_repeated_throughput(benchmark: _BenchmarkFixture) -> None:
    """Benchmarks repeated extraction throughput on the current valid hot path."""
    result = benchmark.pedantic(
        extract,
        args=(LARGE_VALID_JSON, Invoice),
        iterations=20,
        rounds=10,
    )

    assert result.repair_applied is False
    assert result.data.invoice_id == 9001
