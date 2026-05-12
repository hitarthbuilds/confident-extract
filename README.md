# confident-extract

[![CI](https://img.shields.io/github/actions/workflow/status/hitarthbuilds/confident-extract/ci.yml?branch=master&label=CI)](https://github.com/hitarthbuilds/confident-extract/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/badge/PyPI-0.1.0a1%20pending-blue)](https://pypi.org/project/confident-extract/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://pypi.org/project/confident-extract/)
[![License](https://img.shields.io/github/license/hitarthbuilds/confident-extract)](https://github.com/hitarthbuilds/confident-extract/blob/master/LICENSE)

`confident-extract` is a small Python library for deterministic structured extraction from noisy JSON-like model output.

The current public alpha surface is synchronous and `msgspec`-first:

- `from confident_extract import extract`
- deterministic preprocessing and JSON repair
- strict `msgspec.Struct` validation
- lightweight result metadata around the validated output

## Project overview

The library is built for the common case where an upstream model or OCR system returns JSON-like text that is close to valid, but not always valid enough to parse or validate directly.

The current sync pipeline is:

1. preprocess raw text
2. repair malformed JSON conservatively
3. validate against a `msgspec.Struct` schema
4. return a typed `ExtractionResult`

The package does not currently include provider adapters, retries, async APIs, streaming, confidence scoring, or a pydantic bridge.

## Install

Install the published package:

```bash
python -m pip install confident-extract
```

Install for local development:

```bash
python -m pip install -e ".[dev]"
```

## Quickstart example

```python
import msgspec

from confident_extract import extract


class Invoice(msgspec.Struct):
    invoice_id: int
    status: str
    total_cents: int


result = extract(
    text='{"invoice_id": 42, "status": "paid", "total_cents": 1999}',
    schema=Invoice,
)

assert result.data == Invoice(invoice_id=42, status="paid", total_cents=1999)
assert result.repair_applied is False
```

## Malformed JSON repair example

```python
import msgspec

from confident_extract import extract


class Invoice(msgspec.Struct):
    invoice_id: int
    status: str
    total_cents: int


raw = "{invoice_id: 42, status: 'paid', total_cents: 1999,}"
result = extract(text=raw, schema=Invoice)

assert result.data.status == "paid"
assert result.repair_applied is True
assert result.repaired_text == (
    '{"invoice_id": 42, "status": "paid", "total_cents": 1999}'
)
```

## Nested schema example

```python
import msgspec

from confident_extract import extract


class Contact(msgspec.Struct):
    email: str
    phone: str | None = None


class Customer(msgspec.Struct):
    name: str
    contact: Contact


class Invoice(msgspec.Struct):
    invoice_id: int
    customer: Customer
    tags: list[str]


raw = """
{
  "invoice_id": 7,
  "customer": {
    "name": "Acme",
    "contact": {"email": "ops@example.com", "phone": "123"}
  },
  "tags": ["paid", "net30"]
}
"""

result = extract(text=raw, schema=Invoice)

assert result.data.customer.contact.email == "ops@example.com"
assert result.data.tags == ["paid", "net30"]
```

## Benchmark snapshot

Current local measurements were captured on May 12, 2026 with Python 3.13.5 using:

```bash
python -m pytest benchmarks/test_extract_benchmarks.py --benchmark-json /tmp/confident_extract_benchmarks.json
```

These are local measurements only. They are useful for regression tracking, not public performance claims.

| Path | Scenario | p50 | p99 | Throughput |
| --- | --- | ---: | ---: | ---: |
| `preprocess()` | already-valid JSON | `2.17 us` | `2.46 us` | `462k ops/s` |
| `preprocess()` | fenced ~10KB payload | `4.25 us` | `13.04 us` | `215k ops/s` |
| `repair()` | valid fast path | `6.21 us` | `31.25 us` | `145k ops/s` |
| `repair()` | trailing comma repair | `123.50 us` | `328.29 us` | `7.5k ops/s` |
| `repair()` | multi-strategy repair | `611.38 us` | `965.96 us` | `1.7k ops/s` |
| `validate_with_msgspec()` | nested decoded payload | `3.00 us` | `3.21 us` | `333k ops/s` |
| `validate_with_msgspec()` | ~10KB decoded payload | `27.75 us` | `39.00 us` | `34.6k ops/s` |
| `extract()` | valid fast path | `7.42 us` | `13.88 us` | `123k ops/s` |
| `extract()` | trailing comma repair | `73.50 us` | `172.63 us` | `13.2k ops/s` |
| `extract()` | multi-strategy nested repair | `406.83 us` | `820.83 us` | `2.2k ops/s` |
| `extract()` | ~10KB nested payload | `92.83 us` | `167.75 us` | `10.5k ops/s` |
| `extract()` | repeated ~10KB throughput | `94.69 us` | `96.21 us` | `10.6k ops/s` |

### Benchmark caveats

- The current suite is local, deterministic, and provider-free.
- Outlier behavior will vary by machine, Python version, and thermal state.
- The current repo does not yet publish benchmark baselines from CI runners.
- Instructor, Guardrails, and LangChain comparisons are planned, but not yet implemented in this repository.

### How to run benchmarks

```bash
python -m pytest benchmarks/test_extract_benchmarks.py
python -m pytest benchmarks/test_extract_benchmarks.py --benchmark-sort=mean
python -m pytest benchmarks/test_extract_benchmarks.py --benchmark-json /tmp/confident_extract_benchmarks.json
```

## Architecture flow diagram

```text
raw input text
    |
    v
preprocess(text)
    |
    v
repair(preprocessed_text)
    |
    v
validate_with_msgspec(parsed payload, schema)
    |
    v
ExtractionResult[T]
  - data
  - repair_applied
  - repair_attempts
  - raw_input
  - repaired_text
  - latency_ms
```

## Feature list

- Minimal sync API: `extract(text, schema=Invoice)`
- Conservative preprocessing for markdown fences, whitespace normalization, and escaped JSON
- Deterministic JSON repair for trailing commas, unterminated containers, single quotes, and bare keys
- Strict `msgspec.Struct` validation with field-path extraction on failures
- Frozen, slotted extraction result contract
- Package-root exports for the public sync API
- Local benchmark coverage for preprocess, repair, validation, and full extraction

## Roadmap

- Stabilize the sync extraction API for `0.1.x`
- Add the optional pydantic bridge outside the hot path
- Add async and streaming APIs
- Add provider adapters for live model integrations
- Add confidence scoring and retry routing
- Add reproducible cross-library benchmark comparisons

## Contribution and dev setup

`AGENTS.md` is the repo-level implementation contract. Read it before changing the code.

Local setup:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pre-commit install
```

Quality gates:

```bash
python -m ruff check .
python -m mypy .
python -m pytest
```

Benchmark and release checks:

```bash
python -m pytest benchmarks/test_extract_benchmarks.py
python -m build
twine check dist/*
```

For contributor expectations, issue filing guidance, and release checks, see [CONTRIBUTING.md](https://github.com/hitarthbuilds/confident-extract/blob/master/CONTRIBUTING.md).
