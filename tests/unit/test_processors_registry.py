"""Unit tests for processor registry."""

import pytest

from backend.processors.base import AbstractProcessor, ProcessingResult
from backend.processors.registry import (
    get_processor,
    list_processor_types,
    register_processor,
)


@register_processor
class MockProcessor(AbstractProcessor):
    processor_type = "mock_test_processor"

    async def process(self, records, prompt_template, config):
        return ProcessingResult(success=True, enrichments=[{}] * len(records))


def test_register_processor():
    types = list_processor_types()
    assert "mock_test_processor" in types


def test_get_processor_valid():
    proc = get_processor("mock_test_processor")
    assert proc.processor_type == "mock_test_processor"


def test_get_processor_invalid():
    with pytest.raises(ValueError, match="Unknown processor type"):
        get_processor("definitely_not_registered")


@pytest.mark.asyncio
async def test_mock_processor_process():
    proc = get_processor("mock_test_processor")
    records = [object(), object(), object()]
    result = await proc.process(records, "template", {})
    assert result.success is True
    assert len(result.enrichments) == 3
