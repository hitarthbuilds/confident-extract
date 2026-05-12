# confident-extract

`confident-extract` is a production-oriented Python package for schema-safe structured extraction from noisy AI output.

This repository currently implements **Phase 1 only**:

- packaging and dependency metadata
- strict linting, typing, and test configuration
- GitHub Actions CI
- pre-commit hooks
- package scaffolding for the planned extraction pipeline

No extraction logic ships yet. That is intentional so Phase 1 stays aligned with the PRD and avoids placeholder abstractions.

## Requirements

- Python 3.11+

## Install

```bash
python -m pip install -e ".[dev]"
```

## Quality Gates

```bash
python -m ruff check .
python -m mypy .
python -m pytest
python -c "import confident_extract"
```

## Planned Package Layout

```text
confident_extract/
├── __init__.py
├── core/
├── repair/
├── validators/
├── confidence/
├── retry/
└── providers/
```

