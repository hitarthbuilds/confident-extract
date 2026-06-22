# confident-extract — Structured Extraction from LLM Output

[![CI](https://img.shields.io/github/actions/workflow/status/hitarthbuilds/confident-extract/ci.yml?branch=master&label=CI)](https://github.com/hitarthbuilds/confident-extract/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/confident-extract)](https://pypi.org/project/confident-extract/)
[![PyPI downloads](https://img.shields.io/pypi/dm/confident-extract)](https://pypi.org/project/confident-extract/)
[![Python versions](https://img.shields.io/pypi/pyversions/confident-extract)](https://pypi.org/project/confident-extract/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/hitarthbuilds/confident-extract/blob/master/LICENSE)
[![Typed](https://img.shields.io/badge/typing-typed-blue)](https://mypy-lang.org/)

**Zero LLM round-trips. Microsecond latency. Confidence score on every result.**

`confident-extract` repairs malformed JSON from LLM or OCR output deterministically and validates it against your schema — no extra model calls, no network, no randomness. It works with `msgspec`, `pydantic`, and standard Python dataclasses.

```python
from confident_extract import extract

result = extract(llm_output_text, Invoice)

result.data               # Invoice — fully typed and validated
result.confidence.score   # 0.95 — how clean was the input?
result.confidence.label   # "high"
result.strategy_trace     # ("remove_trailing_commas",)
result.latency_ms         # 8.3
```

---

## Table of Contents

- [Why confident-extract?](#why-confident-extract)
- [Install](#install)
- [Quickstart with Anthropic](#quickstart-with-anthropic)
- [Quickstart with OpenAI](#quickstart-with-openai)
- [Schema support: msgspec, Pydantic, dataclass](#schema-support)
- [What the repair engine fixes](#what-the-repair-engine-fixes)
- [Confidence scoring](#confidence-scoring)
- [Batch extraction](#batch-extraction)
- [Async API](#async-api)
- [Confidence-based routing and fallback](#confidence-based-routing-and-fallback)
- [Custom repair strategies](#custom-repair-strategies)
- [Performance](#performance)
- [How it compares](#how-it-compares-to-alternatives)
- [Architecture](#architecture)
- [FAQ](#faq)
- [GitHub topics](#github-topics)

---

## Why confident-extract?

When you ask an LLM to return JSON, the output is *almost* valid — until it isn't. The problem is deterministic:

- Trailing commas: `{"id": 1,}`
- Single quotes: `{'id': 1}`
- Bare keys: `{id: 1}`
- Python literals: `{"active": True}`
- Comments: `{"id": 1 // primary key}`
- JSON buried in prose: `"Here is the data: {...} — done."`

You have three choices:

| Approach | Extra cost | Latency | Reliability |
|---|---|---|---|
| Retry with structured-output prompt | +1 LLM call ($$$) | +seconds | Good |
| Parse and hope (`json.loads`) | zero | ~0 µs | Fragile |
| **confident-extract** | **zero** | **7–400 µs** | **High + scored** |

`confident-extract` is the *first* pass — deterministic, offline, typed, and scored. If the confidence is too low, *then* retry.

---

## Install

```bash
# Core (msgspec + orjson only — no LLM SDK required)
pip install confident-extract

# With Pydantic v2 support
pip install "confident-extract[pydantic]"

# With Anthropic adapter (extract directly from Message objects)
pip install "confident-extract[anthropic]"

# With OpenAI adapter (extract directly from ChatCompletion objects)
pip install "confident-extract[openai]"
```

---

## Quickstart with Anthropic

```python
import anthropic
import msgspec
from confident_extract.providers.anthropic import extract_from_response


class Invoice(msgspec.Struct):
    invoice_id: int
    vendor: str
    total_cents: int
    paid: bool


client = anthropic.Anthropic()
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=512,
    messages=[{"role": "user", "content": "Return the invoice JSON for order #42."}],
)

result = extract_from_response(message, Invoice)

print(result.data.invoice_id)        # 42
print(result.data.paid)              # True
print(result.confidence.label)       # "high"
print(result.confidence.score)       # 0.95
print(result.repair_applied)         # False — model returned clean JSON
print(result.strategy_trace)         # ()
```

Async version:
```python
from confident_extract.providers.anthropic import extract_from_response_async
result = await extract_from_response_async(message, Invoice)
```

---

## Quickstart with OpenAI

```python
import openai
from pydantic import BaseModel
from confident_extract.providers.openai import extract_from_response


class Invoice(BaseModel):
    invoice_id: int
    vendor: str
    total_cents: int


client = openai.OpenAI()
completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Return the invoice JSON for order #42."}],
)

result = extract_from_response(completion, Invoice)

print(result.data.vendor)
print(result.confidence.score)
```

---

## Schema support

`extract()` accepts three schema types with no extra configuration.

### msgspec.Struct — fastest, zero-allocation validation

```python
import msgspec
from confident_extract import extract


class LineItem(msgspec.Struct):
    sku: str
    quantity: int
    unit_price_cents: int


result = extract('{"sku": "ABC-1", "quantity": 3, "unit_price_cents": 999}', LineItem)
assert result.data.sku == "ABC-1"
```

### Pydantic v2 BaseModel — most popular

```python
from pydantic import BaseModel, field_validator
from confident_extract import extract


class LineItem(BaseModel):
    sku: str
    quantity: int
    unit_price_cents: int

    @field_validator("quantity")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v


result = extract('{"sku": "ABC-1", "quantity": 3, "unit_price_cents": 999}', LineItem)
assert result.data.quantity == 3
```

### Python dataclass — standard library

```python
from dataclasses import dataclass
from confident_extract import extract


@dataclass
class LineItem:
    sku: str
    quantity: int
    unit_price_cents: int


result = extract('{"sku": "ABC-1", "quantity": 3, "unit_price_cents": 999}', LineItem)
assert result.data.sku == "ABC-1"
```

---

## What the repair engine fixes

All repairs are deterministic. No LLM involved. Each strategy is applied in order and skipped if it does not mutate the input. The engine stops at the first clean parse.

| Problem | Input example | Strategy |
|---|---|---|
| JSON buried in prose | `"Result: {...} — done."` | `extract_json_from_prose` |
| C-style comments | `{"id": 1 // key\n}` | `strip_json_comments` |
| Python literals | `{"active": True, "val": None}` | `fix_python_literals` |
| Trailing commas | `{"a": 1, "b": [1, 2,],}` | `remove_trailing_commas` |
| Truncated JSON | `{"id": 1, "name": "Ac` | `close_unterminated_json` |
| Single-quoted strings | `{'key': 'value'}` | `normalize_single_quotes` |
| Bare/unquoted keys | `{id: 1, name: "Acme"}` | `repair_unquoted_keys` |
| Markdown code fences | ` ```json\n{...}\n``` ` | preprocessor |
| Escaped JSON strings | `"{\"id\": 1}"` | preprocessor |

### Malformed JSON repair example

```python
from confident_extract import extract
import msgspec


class Invoice(msgspec.Struct):
    invoice_id: int
    status: str
    total_cents: int


# Single quotes + bare keys + trailing comma — all fixed in one pass
raw = "{invoice_id: 99, status: 'paid', total_cents: 4999,}"
result = extract(raw, Invoice)

assert result.data.status == "paid"
assert result.repair_applied is True
assert result.repair_attempts == 2
assert "normalize_single_quotes" in result.strategy_trace
assert "repair_unquoted_keys" in result.strategy_trace
```

### Prose-wrapped JSON

```python
raw = """
I analyzed the order and here are the details:

{"invoice_id": 42, "status": "shipped", "total_cents": 5000}

Let me know if you need anything else.
"""
result = extract(raw, Invoice)
assert result.data.invoice_id == 42
assert result.strategy_trace[0] == "extract_json_from_prose"
```

---

## Confidence scoring

Every `ExtractionResult` carries a `ConfidenceScore` computed from which repair strategies fired and their severity.

```python
result.confidence.score          # float 0.0–1.0 (1.0 = no repair needed)
result.confidence.label          # "high" (≥0.8) / "medium" (≥0.5) / "low" (<0.5)
result.confidence.repair_penalty # total deduction from 1.0
result.strategy_trace            # ("normalize_single_quotes", "repair_unquoted_keys")
```

| Strategy fired | Confidence penalty |
|---|---|
| `extract_json_from_prose` | −0.20 |
| `close_unterminated_json` | −0.15 |
| `normalize_single_quotes` | −0.10 |
| `repair_unquoted_keys` | −0.10 |
| `fix_python_literals` | −0.08 |
| `strip_json_comments` | −0.05 |
| `remove_trailing_commas` | −0.05 |

Use confidence to decide whether to accept, retry, or escalate:

```python
result = extract(text, Invoice)
if result.confidence.label == "high":
    store(result.data)
elif result.confidence.label == "medium":
    store_with_flag(result.data)
else:
    queue_for_human_review(result)
```

---

## Batch extraction

Process many texts in parallel with a thread pool:

```python
from confident_extract import extract_batch

texts = [msg1.content[0].text, msg2.content[0].text, msg3.content[0].text]
results = extract_batch(texts, Invoice)

for r in results:
    print(r.data.invoice_id, r.confidence.label)
```

With `ordered=False` for slightly lower latency on uneven workloads:

```python
results = extract_batch(texts, Invoice, ordered=False, max_workers=8)
```

Extract lists of items in bulk:

```python
from confident_extract import extract_batch_list

results = extract_batch_list(array_texts, LineItem)
# results: list[ExtractionResult[list[LineItem]]]
```

---

## Async API

All functions have async equivalents that offload work to a thread pool:

```python
from confident_extract import extract_async, extract_list_async, extract_batch_async

# Single async extraction
result = await extract_async(text, Invoice)

# Async list extraction
result = await extract_list_async(array_text, LineItem)

# Async batch with concurrency cap
results = await extract_batch_async(texts, Invoice, max_concurrency=16)
```

---

## Confidence-based routing and fallback

### extract_with_routing — automatic fallback on low confidence

```python
from confident_extract import extract_with_routing, RoutingConfig

def reprompt(result):
    """Re-prompt the model with a stricter instruction."""
    new_text = my_llm_client.ask_again(result.raw_input)
    return extract(new_text, Invoice)

config = RoutingConfig(min_confidence=0.8, on_low_confidence=reprompt)
result = extract_with_routing(text, Invoice, config=config)
```

### Raise on low confidence

```python
from confident_extract import LowConfidenceError

config = RoutingConfig(min_confidence=0.7, raise_on_low_confidence=True)
try:
    result = extract_with_routing(text, Invoice, config=config)
except LowConfidenceError as e:
    print(e.result.strategy_trace)
```

### filter_by_confidence — split a batch

```python
from confident_extract import filter_by_confidence

confident, uncertain = filter_by_confidence(results, min_score=0.8)
process(confident)
review_queue.extend(uncertain)
```

---

## Custom repair strategies

Register your own repair strategy for domain-specific LLM quirks:

```python
from confident_extract import register_strategy

def fix_nan(text: str) -> str:
    """Replace JavaScript NaN with JSON null."""
    if "NaN" not in text:
        return text  # return unchanged to skip — engine checks string identity
    return text.replace(": NaN", ": null").replace(":NaN", ":null")

register_strategy("fix_nan", fix_nan)
# All future extract() calls will try fix_nan after built-in strategies
```

Custom strategies appear in `result.strategy_trace` with the name you registered. Use `unregister_strategy("fix_nan")` to remove, or `list_strategies()` to inspect.

---

## ExtractionResult reference

```python
@dataclass(frozen=True, slots=True)
class ExtractionResult(Generic[T]):
    data: T                          # Validated schema instance
    repair_applied: bool             # Whether any strategy mutated the input
    repair_attempts: int             # Number of strategies that mutated
    raw_input: str                   # Original text as received
    repaired_text: str               # Text after repair, before validation
    latency_ms: float                # End-to-end wall-clock time in ms
    confidence: ConfidenceScore      # score, label, repair_penalty
    strategy_trace: tuple[str, ...]  # Names of strategies that fired, in order
```

---

## Performance

All measurements on Apple M-series, Python 3.13, May 2026.

| Scenario | p50 | p99 | Throughput |
|---|---:|---:|---:|
| `preprocess()` — already-valid JSON | `1.1 µs` | `1.5 µs` | `890k ops/s` |
| `preprocess()` — fenced ~10KB | `4.3 µs` | `13 µs` | `215k ops/s` |
| `repair()` — valid fast path | `6.2 µs` | `31 µs` | `145k ops/s` |
| `repair()` — trailing comma | `124 µs` | `328 µs` | `7.5k ops/s` |
| `repair()` — multi-strategy | `611 µs` | `966 µs` | `1.7k ops/s` |
| `extract()` — valid fast path | **7.4 µs** | `14 µs` | **123k ops/s** |
| `extract()` — trailing comma | `74 µs` | `173 µs` | `13k ops/s` |
| `extract()` — multi-strategy | `407 µs` | `821 µs` | `2.2k ops/s` |
| `extract()` — ~10KB payload | `93 µs` | `168 µs` | `10.5k ops/s` |

The preprocessor fast path skips fence-stripping for bare JSON input, cutting overhead by ~50% on the hot path.

Run benchmarks:
```bash
python -m pytest benchmarks/ --benchmark-sort=mean
```

---

## How it compares to alternatives

| | **confident-extract** | instructor | guardrails | json-repair |
|---|:---:|:---:|:---:|:---:|
| Extra LLM calls to fix bad JSON | **0** | 1–N | 1–N | 0 |
| Confidence score on output | **✓** | — | — | — |
| msgspec.Struct support | **✓** | — | — | — |
| Pydantic v2 support | **✓** | ✓ | ✓ | — |
| Dataclass support | **✓** | — | — | — |
| Async API | **✓** | ✓ | partial | — |
| Batch extraction | **✓** | — | — | — |
| Confidence routing / fallback | **✓** | — | — | — |
| Custom repair strategies | **✓** | — | — | — |
| Works offline | **✓** | — | — | ✓ |
| Provider adapters (Anthropic, OpenAI) | **✓** | ✓ | ✓ | — |
| Core deps: only orjson + msgspec | **✓** | — | — | ✓ |

**Recommended pattern:** use `confident-extract` as the first pass. If `confidence.label == "low"`, optionally retry with `instructor` or a structured-output prompt. This eliminates retry costs for the ~80–90% of outputs that are clean or lightly malformed.

---

## Architecture

```
raw input text
      │
      ▼
 preprocess(text)           strip fences · CRLF · unwrap escaped JSON
      │                     fast-path: skips fence work for bare JSON
      ▼
 repair(preprocessed)       try_orjson_parse → on failure, apply in order:
      │                       1. extract_json_from_prose
      │                       2. strip_json_comments
      │                       3. fix_python_literals
      │                       4. remove_trailing_commas
      │                       5. close_unterminated_json
      │                       6. normalize_single_quotes
      │                       7. repair_unquoted_keys
      │                       + any custom registered strategies
      ▼
 validate(payload, schema)  auto-detect schema type → route:
      │                       msgspec.Struct    → msgspec.convert (strict)
      │                       pydantic.BaseModel → model_validate
      │                       dataclass          → msgspec.convert (lenient)
      ▼
 compute_confidence(trace)  score = 1.0 − Σ(per-strategy penalties)
      │                     capped at [0.10, 1.0], labeled "high"/"medium"/"low"
      ▼
 ExtractionResult[T]
```

---

## FAQ

**How do I extract structured data from LLM output in Python?**
`pip install confident-extract` then `result = extract(llm_text, MySchema)`. Works with msgspec, Pydantic, and dataclasses.

**Does it work without an internet connection?**
Yes. The entire pipeline runs in-process with no network calls.

**What is the difference between confident-extract and instructor?**
`instructor` retries the model when JSON is invalid, spending another LLM call. `confident-extract` repairs the JSON deterministically in microseconds with no extra cost. Use both together: confident-extract as the fast first pass, instructor as the fallback on `confidence.label == "low"`.

**What is the difference between confident-extract and json-repair?**
`json-repair` returns a fixed string. `confident-extract` validates the fixed string against your schema, returns a typed object, and gives you a confidence score.

**Does it support async?**
Yes: `await extract_async(text, schema)`, `await extract_batch_async(texts, schema)`.

**How do I handle batch LLM responses?**
`results = extract_batch(list_of_texts, Invoice)` — runs in a thread pool. Async: `await extract_batch_async(texts, Invoice)`.

**How do I add my own JSON repair logic?**
`register_strategy("my_fix", my_fn)` — custom strategies run after built-ins and appear in `strategy_trace`.

---

## GitHub topics

To maximize GitHub discoverability, the repository uses these topics:

`llm` · `json-repair` · `structured-extraction` · `msgspec` · `pydantic` · `orjson` · `schema-validation` · `anthropic` · `openai` · `information-extraction` · `nlp` · `python` · `async` · `confidence-scoring` · `json-parsing`

---

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Quality gates:
```bash
ruff check .
mypy .
pytest
pytest benchmarks/ --benchmark-sort=mean
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributor expectations and release steps.

---

## Citation

If you use `confident-extract` in research, please cite it using the [CITATION.cff](CITATION.cff) file. GitHub renders a "Cite this repository" button automatically.

---

*Built by [Hitarth Desai](https://github.com/hitarthbuilds). MIT License.*
