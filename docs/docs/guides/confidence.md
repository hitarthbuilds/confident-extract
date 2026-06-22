# Confidence Scoring

Every `ExtractionResult` carries a `ConfidenceScore` that tells you how much repair was needed to produce the result.

## Reading the score

```python
result = extract(text, Invoice)

result.confidence.score          # float 0.0–1.0
result.confidence.label          # "high" / "medium" / "low"
result.confidence.repair_penalty # total deduction from 1.0
result.strategy_trace            # tuple of strategy names that fired
```

## Score model

The score starts at `1.0` and deducts a penalty for each repair strategy that fired:

| Strategy | Penalty |
|---|---|
| `extract_json_from_prose` | −0.20 |
| `close_unterminated_json` | −0.15 |
| `fix_python_literals` | −0.08 |
| `normalize_single_quotes` | −0.10 |
| `repair_unquoted_keys` | −0.10 |
| `strip_json_comments` | −0.05 |
| `remove_trailing_commas` | −0.05 |
| custom (default) | −0.10 |

Total penalty is capped at `0.90`, so the minimum score is `0.10`.

## Labels

| Label | Score range | Meaning |
|---|---|---|
| `"high"` | ≥ 0.80 | Clean input or minor repairs |
| `"medium"` | 0.50–0.79 | Moderate repairs needed |
| `"low"` | < 0.50 | Heavy reconstruction |

## Acting on confidence

### Route low-confidence results to a fallback

```python
from confident_extract import extract_with_routing, RoutingConfig

def reprompt(result):
    new_text = call_llm_with_stricter_prompt(result.raw_input)
    return extract(new_text, Invoice)

config = RoutingConfig(min_confidence=0.8, on_low_confidence=reprompt)
result = extract_with_routing(text, Invoice, config=config)
```

### Raise on low confidence

```python
from confident_extract import extract_with_routing, RoutingConfig, LowConfidenceError

config = RoutingConfig(min_confidence=0.8, raise_on_low_confidence=True)
try:
    result = extract_with_routing(text, Invoice, config=config)
except LowConfidenceError as e:
    print(e.result.strategy_trace)  # inspect what went wrong
```

### Filter a batch

```python
from confident_extract import extract_batch, filter_by_confidence

results = extract_batch(texts, Invoice)
confident, uncertain = filter_by_confidence(results, min_score=0.8)

# Send confident results downstream
process(confident)

# Queue uncertain for review
review_queue.extend(uncertain)
```
