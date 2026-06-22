"""OpenAI provider adapter for confident-extract."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletion

from confident_extract.core.extractor import extract, extract_async

if TYPE_CHECKING:
    from confident_extract.core.result import ExtractionResult

T = TypeVar("T")


def _get_text(response: ChatCompletion) -> str:
    """Pulls the text content from the first choice of an OpenAI ChatCompletion."""
    content = response.choices[0].message.content
    if content is None:
        msg = (
            "No text content in the OpenAI response. "
            "The model may have returned a tool_call instead of plain text."
        )
        raise ValueError(msg)
    return content


def extract_from_response(response: ChatCompletion, schema: type[T]) -> ExtractionResult[T]:
    """Extracts a typed schema instance from an OpenAI ``ChatCompletion`` response.

    Requires the ``openai`` extra: ``pip install 'confident-extract[openai]'``.

    Args:
        response: A ``ChatCompletion`` returned by the OpenAI client.
        schema: Target schema type. Supports msgspec Structs, Pydantic v2
            BaseModel subclasses, and dataclasses.

    Returns:
        An ``ExtractionResult`` containing the validated data and repair metadata.

    Example::

        import openai
        from confident_extract.providers.openai import extract_from_response

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Return invoice JSON for order #42."}],
        )
        result = extract_from_response(response, Invoice)
        print(result.data.invoice_id)
        print(result.confidence.score)   # 0.0 - 1.0
    """
    try:
        from openai.types.chat import ChatCompletion  # noqa: F401
    except ImportError as exc:
        msg = (
            "The openai package is required for this adapter. "
            "Install it with: pip install 'confident-extract[openai]'"
        )
        raise ImportError(msg) from exc

    return extract(_get_text(response), schema)


async def extract_from_response_async(
    response: ChatCompletion,
    schema: type[T],
) -> ExtractionResult[T]:
    """Async variant of :func:`extract_from_response`.

    Args:
        response: A ``ChatCompletion``.
        schema: Target schema type.

    Returns:
        Same ``ExtractionResult`` as :func:`extract_from_response`.
    """
    try:
        from openai.types.chat import ChatCompletion  # noqa: F401
    except ImportError as exc:
        msg = (
            "The openai package is required for this adapter. "
            "Install it with: pip install 'confident-extract[openai]'"
        )
        raise ImportError(msg) from exc

    return await extract_async(_get_text(response), schema)
