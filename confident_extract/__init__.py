"""Top-level package exports for confident-extract."""

from importlib.metadata import PackageNotFoundError, version

from confident_extract.confidence.scorer import ConfidenceScore
from confident_extract.core.batch import extract_batch, extract_batch_async, extract_batch_list
from confident_extract.core.extractor import (
    extract,
    extract_async,
    extract_list,
    extract_list_async,
)
from confident_extract.core.result import ExtractionResult
from confident_extract.core.routing import (
    LowConfidenceError,
    RoutingConfig,
    extract_with_routing,
    filter_by_confidence,
)
from confident_extract.repair.registry import (
    list_strategies,
    register_strategy,
    unregister_strategy,
)
from confident_extract.validators.msgspec_adapter import (
    MsgspecValidationError,
    ValidationError,
)
from confident_extract.validators.pydantic_adapter import (
    PydanticFieldError,
    PydanticValidationError,
)

try:
    __version__ = version("confident-extract")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "ConfidenceScore",
    "ExtractionResult",
    "LowConfidenceError",
    "MsgspecValidationError",
    "PydanticFieldError",
    "PydanticValidationError",
    "RoutingConfig",
    "ValidationError",
    "__version__",
    "extract",
    "extract_async",
    "extract_batch",
    "extract_batch_async",
    "extract_batch_list",
    "extract_list",
    "extract_list_async",
    "extract_with_routing",
    "filter_by_confidence",
    "list_strategies",
    "register_strategy",
    "unregister_strategy",
]
