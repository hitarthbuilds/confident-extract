"""Tests for extract_list and extract_async."""

from __future__ import annotations

import asyncio

import msgspec
import pytest

from confident_extract import extract_async, extract_list, extract_list_async


class Tag(msgspec.Struct):
    name: str
    value: int


class TestExtractList:
    def test_valid_json_array(self) -> None:
        raw = '[{"name": "alpha", "value": 1}, {"name": "beta", "value": 2}]'
        result = extract_list(raw, Tag)
        assert len(result.data) == 2
        assert result.data[0].name == "alpha"
        assert result.data[1].value == 2

    def test_malformed_array_repaired(self) -> None:
        raw = "[{name: 'alpha', value: 1}, {name: 'beta', value: 2},]"
        result = extract_list(raw, Tag)
        assert len(result.data) == 2
        assert result.repair_applied is True

    def test_max_items_truncates(self) -> None:
        raw = '[{"name": "a", "value": 1}, {"name": "b", "value": 2}, {"name": "c", "value": 3}]'
        result = extract_list(raw, Tag, max_items=2)
        assert len(result.data) == 2

    def test_non_array_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="JSON array"):
            extract_list('{"name": "x", "value": 1}', Tag)

    def test_confidence_attached(self) -> None:
        raw = '[{"name": "x", "value": 9}]'
        result = extract_list(raw, Tag)
        assert result.confidence.score == 1.0
        assert result.confidence.label == "high"

    def test_empty_array(self) -> None:
        result = extract_list("[]", Tag)
        assert result.data == []


class TestExtractAsync:
    def test_async_returns_same_as_sync(self) -> None:
        import confident_extract as ce

        raw = '{"name": "async_tag", "value": 42}'
        sync_result = ce.extract(raw, Tag)
        async_result = asyncio.get_event_loop().run_until_complete(
            extract_async(raw, Tag)
        )
        assert async_result.data == sync_result.data
        assert async_result.repair_applied == sync_result.repair_applied

    def test_async_list(self) -> None:
        raw = '[{"name": "x", "value": 1}]'
        result = asyncio.get_event_loop().run_until_complete(
            extract_list_async(raw, Tag)
        )
        assert result.data[0].name == "x"
