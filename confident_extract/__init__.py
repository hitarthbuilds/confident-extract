"""Top-level package exports for confident-extract."""

from importlib.metadata import PackageNotFoundError, version

from confident_extract.core.extractor import extract
from confident_extract.core.result import ExtractionResult
from confident_extract.validators.msgspec_adapter import (
    MsgspecValidationError,
    ValidationError,
)

try:
    __version__ = version("confident-extract")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "ExtractionResult",
    "MsgspecValidationError",
    "ValidationError",
    "__version__",
    "extract",
]
