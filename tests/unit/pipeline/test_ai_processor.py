"""Unit tests for ai_processor pipeline step."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.pipeline.ai_processor import process_with_ai
from backend.processors.base import ProcessingResult


@pytest.mark.asyncio
async def test_process_with_ai_no_config():
    records = [MagicMock()]
    await process_with_ai(records, None)
    # Should do nothing


@pytest.mark.asyncio
async def test_process_with_ai_no_records():
    await process_with_ai([], {"processor_type": "claude"})
    # Should do nothing


@pytest.mark.asyncio
async def test_process_with_ai_unknown_processor():
    records = [MagicMock()]
    # Should silently skip unknown processor
    await process_with_ai(records, {"processor_type": "unknown_processor_xyz"})


@pytest.mark.asyncio
async def test_process_with_ai_enriches_records():
    records = [MagicMock(), MagicMock()]
    for r in records:
        r.ai_enrichment = None
        r.status = "normalized"

    enrichments = [{"summary": "Summary 1"}, {"summary": "Summary 2"}]
    mock_result = ProcessingResult(success=True, enrichments=enrichments)
    mock_processor = AsyncMock()
    mock_processor.process = AsyncMock(return_value=mock_result)

    with patch("backend.pipeline.ai_processor.get_processor", return_value=mock_processor):
        await process_with_ai(records, {"processor_type": "claude", "prompt_template": "Summarize: {{content}}"})

    assert records[0].ai_enrichment == {"summary": "Summary 1"}
    assert records[1].ai_enrichment == {"summary": "Summary 2"}
    assert records[0].status == "ai_processed"
