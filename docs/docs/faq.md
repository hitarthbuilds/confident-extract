# Frequently Asked Questions

## How do I extract structured data from LLM output in Python?

Use `confident-extract`:

```python
from confident_extract import extract
import msgspec

class Invoice(msgspec.Struct):
    invoice_id: int
    status: str

result = extract(llm_response_text, Invoice)
print(result.data.invoice_id)
```

It handles malformed JSON automatically — single quotes, bare keys, trailing commas, Python literals, and more.

---

## How do I parse JSON from a Claude or ChatGPT response?

Use the provider adapters:

```python
# Anthropic Claude
from confident_extract.providers.anthropic import extract_from_response
result = extract_from_response(anthropic_message, Invoice)

# OpenAI GPT
from confident_extract.providers.openai import extract_from_response
result = extract_from_response(openai_completion, Invoice)
```

Both extract the text content from the response object and run the full repair + validation pipeline.

---

## What is the difference between confident-extract and instructor?

| | confident-extract | instructor |
|---|---|---|
| Additional LLM calls to fix bad JSON | **0** | 1–N |
| Works offline / without a model | **yes** | no |
| Confidence score on output quality | **yes** | no |
| Pydantic support | yes | yes |
| msgspec support | **yes** | no |
| Dataclass support | **yes** | no |

Use `confident-extract` for a fast, cheap first pass. If `confidence.label == "low"`, optionally fall back to a retry via instructor or a structured-output prompt.

---

## What is the difference between confident-extract and json-repair?

`json-repair` fixes JSON strings and returns a string. `confident-extract` fixes JSON *and* validates it against your schema, returning a typed object plus a confidence score. It also handles Python literals, C-style comments, and JSON buried in prose — cases `json-repair` does not cover.

---

## Does confident-extract call any external APIs?

No. The entire pipeline (preprocessing, repair, validation, confidence scoring) runs in-process. No network calls, no LLM, no external services.

---

## How do I use confident-extract with Pydantic?

```python
from pydantic import BaseModel
from confident_extract import extract

class Invoice(BaseModel):
    invoice_id: int
    status: str

result = extract(text, Invoice)  # schema auto-detected
print(result.data.invoice_id)
```

Install the pydantic extra first: `pip install "confident-extract[pydantic]"`.

---

## How do I process multiple LLM responses in parallel?

```python
from confident_extract import extract_batch

results = extract_batch(list_of_texts, Invoice)
for r in results:
    print(r.data, r.confidence.label)
```

For async codebases:

```python
results = await extract_batch_async(texts, Invoice, max_concurrency=8)
```

---

## What does the confidence score mean?

- `1.0` — the input was already valid JSON, no repair needed
- `0.8–1.0` — minor repairs (e.g., trailing comma removed), "high"
- `0.5–0.8` — moderate repairs (e.g., single quotes, bare keys), "medium"
- `<0.5` — heavy reconstruction (e.g., JSON extracted from prose), "low"

Use `result.strategy_trace` to see exactly what was repaired.

---

## How do I add my own repair strategy?

```python
from confident_extract import register_strategy

def fix_nan(text: str) -> str:
    """Replace JavaScript NaN with JSON null."""
    return text.replace(": NaN", ": null").replace(":NaN", ":null")

register_strategy("fix_nan", fix_nan)
# All future extract() calls will now try fix_nan after built-in strategies
```

---

## How do I handle low-confidence results automatically?

```python
from confident_extract import extract_with_routing, RoutingConfig

def my_fallback(result):
    # Re-prompt the model or return a default
    return extract(call_llm_again(result.raw_input), Invoice)

config = RoutingConfig(min_confidence=0.8, on_low_confidence=my_fallback)
result = extract_with_routing(text, Invoice, config=config)
```

---

## What Python versions are supported?

Python 3.11, 3.12, and 3.13. CPython only.

---

## How fast is it?

- Already-valid JSON: **~7 µs** end-to-end
- Minor repair (trailing comma): **~74 µs**
- Multi-strategy repair: **~400 µs**
- Large 10KB payload: **~93 µs**

All measurements on Apple M-series, Python 3.13.

---

## Is there async support?

Yes. All main functions have async equivalents:

```python
await extract_async(text, Invoice)
await extract_list_async(text, Invoice)
await extract_batch_async(texts, Invoice)
```

They run the synchronous pipeline in a thread pool via `asyncio.to_thread`, keeping the event loop free.

---

## How do I cite confident-extract in a paper?

See the [CITATION.cff](https://github.com/hitarthbuilds/confident-extract/blob/master/CITATION.cff) file at the root of the repository. GitHub renders a "Cite this repository" button automatically.
