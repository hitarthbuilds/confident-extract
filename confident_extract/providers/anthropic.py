"""Anthropic provider adapter for confident-extract."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from anthropic.types import Message

from confident_extract.core.extractor import extract, extract_async

if TYPE_CHECKING:
    from confident_extract.core.result import ExtractionResult

T = TypeVar("T")


def _get_text(response: Message) -> str:
    """Pulls the first text block from an Anthropic Message."""
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    msg = "No text content found in Anthropic Message response."
    raise ValueError(msg)


def extract_from_response(response: Message, schema: type[T]) -> ExtractionResult[T]:
    """Extracts a typed schema instance from an Anthropic ``Message`` response.

    Requires the ``anthropic`` extra: ``pip install 'confident-extract[anthropic]'``.

    Args:
        response: An ``anthropic.types.Message`` returned by the Anthropic client.
        schema: Target schema type. Supports msgspec Structs, Pydantic v2
            BaseModel subclasses, and dataclasses.

    Returns:
        An ``ExtractionResult`` containing the validated data and repair metadata.

    Example::

        import anthropic
        from confident_extract.providers.anthropic import extract_from_response

        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Return invoice JSON for order #42."}],
        )
        result = extract_from_response(response, Invoice)
        print(result.data.invoice_id)
        print(result.confidence.label)   # "high" / "medium" / "low"
    """
    try:
        from anthropic.types import Message  # noqa: F401
    except ImportError as exc:
        msg = (
            "The anthropic package is required for this adapter. "
            "Install it with: pip install 'confident-extract[anthropic]'"
        )
        raise ImportError(msg) from exc

    return extract(_get_text(response), schema)


async def extract_from_response_async(
    response: Message,
    schema: type[T],
) -> ExtractionResult[T]:
    """Async variant of :func:`extract_from_response`.

    Args:
        response: An ``anthropic.types.Message``.
        schema: Target schema type.

    Returns:
        Same ``ExtractionResult`` as :func:`extract_from_response`.
    """
    try:
        from anthropic.types import Message  # noqa: F401
    except ImportError as exc:
        msg = (
            "The anthropic package is required for this adapter. "
            "Install it with: pip install 'confident-extract[anthropic]'"
        )
        raise ImportError(msg) from exc

    return await extract_async(_get_text(response), schema)
