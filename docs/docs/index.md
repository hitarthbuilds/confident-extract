# confident-extract

**Deterministic structured extraction from noisy LLM and OCR output.**

Zero LLM round-trips. Microsecond latency. Works with `msgspec`, `pydantic`, and dataclasses.

---

## What is confident-extract?

When you ask an LLM to return JSON, the output is *almost* valid — but "almost" breaks `json.loads`. Traditional solutions retry with the model (expensive) or silently fail. `confident-extract` takes a third path: it repairs the JSON deterministically, validates it against your schema, and tells you exactly how confident it is in the result.

```python
from confident_extract import extract
from confident_extract.providers.anthropic import extract_from_response

result = extract_from_response(anthropic_response, Invoice)

result.data.invoice_id        # typed, validated
result.confidence.score       # 0.0–1.0 — how clean was the input?
result.confidence.label       # "high" / "medium" / "low"
result.strategy_trace         # what was repaired, if anything
```

---

## Features

| Feature | Details |
|---|---|
| **Schema support** | msgspec.Struct, Pydantic v2, dataclasses |
| **7 repair strategies** | prose extraction, comments, Python literals, trailing commas, unterminated containers, single quotes, bare keys |
| **Confidence scoring** | per-strategy penalty model, 3-tier label |
| **Batch extraction** | `extract_batch()` with ThreadPoolExecutor |
| **Async API** | `extract_async()`, `extract_batch_async()` |
| **Provider adapters** | Anthropic, OpenAI one-liners |
| **Routing & fallback** | `extract_with_routing()`, `filter_by_confidence()` |
| **Plugin system** | `register_strategy()` for custom repair |
| **Fast path** | 7 µs for already-valid JSON |

---

## Quick install

```bash
pip install confident-extract                      # core (msgspec + orjson only)
pip install "confident-extract[pydantic]"          # add Pydantic v2
pip install "confident-extract[anthropic]"         # add Anthropic adapter
pip install "confident-extract[openai]"            # add OpenAI adapter
```

---

## 30-second example

```python
import msgspec
from confident_extract import extract

class Invoice(msgspec.Struct):
    invoice_id: int
    status: str
    total_cents: int

# Noisy model output — single quotes, trailing comma, bare keys
raw = "{invoice_id: 99, status: 'paid', total_cents: 4999,}"

result = extract(raw, Invoice)
print(result.data)                # Invoice(invoice_id=99, status='paid', total_cents=4999)
print(result.confidence.label)   # "high" — minor repairs only
print(result.strategy_trace)     # ("normalize_single_quotes", "repair_unquoted_keys", ...)
```

---

## Next steps

- [Quickstart](getting-started/quickstart.md) — full working examples
- [Schema Types](guides/schemas.md) — msgspec, Pydantic, dataclass
- [Confidence Scoring](guides/confidence.md) — interpret and act on scores
- [Provider Adapters](providers/anthropic.md) — Anthropic and OpenAI
- [FAQ](faq.md) — common questions
