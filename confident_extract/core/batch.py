"""Batch extraction for processing multiple texts in parallel."""

from __future__ import annotations

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, TypeVar

from confident_extract.core.extractor import extract, extract_list

if TYPE_CHECKING:
    from confident_extract.core.result import ExtractionResult

T = TypeVar("T")


def extract_batch(
    texts: list[str],
    schema: type[T],
    *,
    max_workers: int | None = None,
    ordered: bool = True,
) -> list[ExtractionResult[T]]:
    """Extracts typed schema instances from a list of raw texts in parallel.

    Uses a ``ThreadPoolExecutor`` to run the extraction pipeline concurrently.
    The GIL is released during orjson parsing and I/O, so wall-clock time
    scales well up to the number of CPU cores for large batches.

    Args:
        texts: List of raw input texts to extract from.
        schema: Target schema type. Supports msgspec Structs, Pydantic v2
            BaseModel subclasses, and dataclasses.
        max_workers: Maximum number of threads. Defaults to
            ``min(len(texts), 16)``.
        ordered: When ``True`` (default), results are returned in the same
            order as ``texts``. When ``False``, results arrive in completion
            order and may be faster for large uneven batches.

    Returns:
        List of ``ExtractionResult`` instances, one per input text.

    Example::

        from confident_extract import extract_batch

        texts = [response1.content[0].text, response2.content[0].text]
        results = extract_batch(texts, Invoice)
        for r in results:
            print(r.data.invoice_id, r.confidence.label)
    """
    if not texts:
        return []

    effective_workers = max_workers or min(len(texts), 16)

    if ordered:
        with ThreadPoolExecutor(max_workers=effective_workers) as pool:
            futures = [pool.submit(extract, text, schema) for text in texts]
            return [f.result() for f in futures]

    results: list[tuple[int, ExtractionResult[T]]] = []
    with ThreadPoolExecutor(max_workers=effective_workers) as pool:
        future_to_index = {
            pool.submit(extract, text, schema): idx for idx, text in enumerate(texts)
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            results.append((idx, future.result()))

    results.sort(key=lambda pair: pair[0])
    return [r for _, r in results]


def extract_batch_list(
    texts: list[str],
    schema: type[T],
    *,
    max_workers: int | None = None,
    max_items: int | None = None,
) -> list[ExtractionResult[list[T]]]:
    """Extracts typed lists from a batch of JSON-array texts in parallel.

    Args:
        texts: List of raw input texts, each expected to contain a JSON array.
        schema: Target item schema type.
        max_workers: Maximum number of threads.
        max_items: Optional per-result item cap passed to :func:`extract_list`.

    Returns:
        List of ``ExtractionResult[list[T]]`` instances, one per input text.
    """
    if not texts:
        return []

    effective_workers = max_workers or min(len(texts), 16)
    _extract_list_partial = functools.partial(extract_list, schema=schema, max_items=max_items)

    with ThreadPoolExecutor(max_workers=effective_workers) as pool:
        futures = [pool.submit(_extract_list_partial, text) for text in texts]
        return [f.result() for f in futures]


async def extract_batch_async(
    texts: list[str],
    schema: type[T],
    *,
    max_concurrency: int = 16,
) -> list[ExtractionResult[T]]:
    """Async variant of :func:`extract_batch` using asyncio semaphore-bounded concurrency.

    Runs each extraction in a thread pool via ``asyncio.to_thread``. Safe to
    ``await`` from any asyncio coroutine without blocking the event loop.

    Args:
        texts: List of raw input texts.
        schema: Target schema type.
        max_concurrency: Maximum number of concurrent thread submissions.

    Returns:
        List of ``ExtractionResult`` instances in input order.
    """
    if not texts:
        return []

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _bounded_extract(text: str) -> ExtractionResult[T]:
        async with semaphore:
            return await asyncio.to_thread(extract, text, schema)

    return list(await asyncio.gather(*[_bounded_extract(t) for t in texts]))
