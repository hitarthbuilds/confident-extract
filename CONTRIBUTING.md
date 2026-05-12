# Contributing

## Scope

`confident-extract` is a narrow library for deterministic structured extraction from noisy JSON-like text.

Before opening a change:

- read [AGENTS.md](AGENTS.md)
- keep the public API minimal
- do not add provider logic, retries, or optional bridges unless the task explicitly requires them
- avoid hidden fallbacks and blocking I/O in the hot path

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pre-commit install
```

## Quality gates

Run these before opening a PR:

```bash
python -m ruff check .
python -m mypy .
python -m pytest
```

## Benchmarks

Run the current local benchmark suite with:

```bash
python -m pytest benchmarks/test_extract_benchmarks.py
python -m pytest benchmarks/test_extract_benchmarks.py --benchmark-sort=mean
python -m pytest benchmarks/test_extract_benchmarks.py --benchmark-json /tmp/confident_extract_benchmarks.json
```

Notes:

- benchmark numbers are local measurements unless explicitly captured from CI
- do not make public performance claims from a single local run
- if a change touches preprocessing, repair, validation, or extraction orchestration, rerun the benchmark suite

## Release checks

Before cutting a release candidate or alpha tag:

```bash
python -m build
twine check dist/*
```

If `dist/` or `build/` already exists from a prior run, remove them and rebuild.

## Pull requests

Keep PRs narrow and traceable:

- one feature area or one layer at a time
- include tests for every changed module
- explain behavior changes and benchmark impact when hot-path code changes

## Issues

Use GitHub issues for concrete bugs, regressions, or feature requests.

For usage questions or local development setup, start from the README and this guide before filing an issue.
