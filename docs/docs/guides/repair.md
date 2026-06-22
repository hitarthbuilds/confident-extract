# Repair Engine

`confident-extract` repairs malformed JSON deterministically — no LLM, no network.

## Built-in strategies

Strategies run in this order. Each strategy is skipped if it does not mutate the input. The engine stops as soon as the result parses cleanly.

### 1. `extract_json_from_prose`

Finds the first balanced `{...}` or `[...]` block in surrounding prose text.

```python
# Input
"Here is the invoice data: {\"id\": 1, \"status\": \"paid\"} — hope that helps!"

# After repair
'{"id": 1, "status": "paid"}'
```

### 2. `strip_json_comments`

Removes C-style `//` line comments and `/* */` block comments.

```python
# Input
'{"id": 1, // primary key\n "status": "paid" /* always */}'

# After repair
'{"id": 1,\n "status": "paid" }'
```

### 3. `fix_python_literals`

Replaces Python `True`, `False`, and `None` with JSON `true`, `false`, and `null`. Respects string boundaries.

```python
# Input
'{"active": True, "deleted": False, "metadata": None}'

# After repair
'{"active": true, "deleted": false, "metadata": null}'
```

### 4. `remove_trailing_commas`

Removes commas before `}` or `]`.

```python
# Input
'{"id": 1, "tags": ["paid", "net30",],}'

# After repair
'{"id": 1, "tags": ["paid", "net30"]}'
```

### 5. `close_unterminated_json`

Appends missing closing braces or brackets for truncated input.

```python
# Input (truncated)
'{"id": 1, "customer": {"name": "Acme"'

# After repair
'{"id": 1, "customer": {"name": "Acme"}}'
```

### 6. `normalize_single_quotes`

Converts single-quoted keys and values to double-quoted JSON strings.

```python
# Input
"{'id': 1, 'status': 'paid'}"

# After repair
'{"id": 1, "status": "paid"}'
```

### 7. `repair_unquoted_keys`

Wraps bare object keys in double quotes.

```python
# Input
'{id: 1, status: "paid"}'

# After repair
'{"id": 1, "status": "paid"}'
```

## Custom strategies

You can register your own strategy to run after the built-ins:

```python
from confident_extract import register_strategy

def fix_nan(text: str) -> str:
    """Replace JavaScript NaN with JSON null."""
    if "NaN" not in text:
        return text  # fast path — return unchanged to skip
    return text.replace(": NaN", ": null").replace(":NaN", ":null")

register_strategy("fix_nan", fix_nan)
```

Custom strategies appear in `result.strategy_trace` and receive confidence penalties just like built-ins. Register a penalty weight by adding your strategy name to the `_STRATEGY_PENALTIES` dict in `confident_extract/confidence/scorer.py` if you want a custom weight; otherwise the default `0.10` penalty applies.

## Preprocessing (before repair)

Before repair strategies run, the preprocessor cleans up common wrapping patterns:

- **Markdown fences** — strips ` ```json\n{...}\n``` ` wrappers
- **CRLF normalization** — converts `\r\n` and `\r` to `\n`
- **Escaped JSON unwrapping** — handles `"{\"id\": 1}"` (JSON-in-string)
- **Fast path** — for bare JSON (starts with `{` or `[`, no ` ``` `), the preprocessor skips fence stripping entirely, saving ~50% of preprocessing time
