# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows semantic versioning pre-release tags for public alpha cuts.

## [Unreleased]

## [0.1.0a1] - 2026-05-12

### Added

- Sync public API at the package root: `extract`, `ExtractionResult`, `MsgspecValidationError`, and `ValidationError`
- Deterministic preprocessing, repair, and `msgspec` validation layers
- Minimal synchronous extraction pipeline with repair metadata and latency measurement
- Unit coverage for preprocess, repair strategies, repair engine, validator adapter, extractor, and package-root API
- Initial local benchmark suite for preprocess, repair, validation, and full extraction
- Public alpha OSS release artifacts: README, contribution guide, changelog, and issue-template config

### Changed

- Package metadata updated for a public alpha release target
- Development extras now include release tooling for `python -m build` and `twine check`
