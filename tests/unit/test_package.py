"""Phase 1 smoke tests for repository scaffolding."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from types import ModuleType

MODULE_NAMES: Final[tuple[str, ...]] = (
    "benchmarks",
    "confident_extract",
    "confident_extract.confidence",
    "confident_extract.core",
    "confident_extract.providers",
    "confident_extract.repair",
    "confident_extract.retry",
    "confident_extract.validators",
)


def test_package_scaffold_imports() -> None:
    """Ensures the Phase 1 scaffold imports without side effects."""
    modules: dict[str, ModuleType] = {
        module_name: importlib.import_module(module_name) for module_name in MODULE_NAMES
    }

    assert modules["confident_extract"].__name__ == "confident_extract"
    assert hasattr(modules["confident_extract"], "__version__")
