"""Unit tests for pipeline collector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.channels.base import ChannelResult
from backend.pipeline.collector import collect


@pytest.mark.asyncio
async def test_collect_dispatches_to_channel():
    source = MagicMock()
    source.channel_type = "rss"
    source.channel_config = {"feed_url": "https://ex.com/feed"}

    expected = ChannelResult.ok([{"title": "Test"}])
    mock_channel = AsyncMock()
    mock_channel.collect = AsyncMock(return_value=expected)

    with patch("backend.pipeline.collector.get_channel", return_value=mock_channel):
        result = await collect(source, {"extra": "param"})

    assert result.success is True
    assert result.count == 1
    mock_channel.collect.assert_awaited_once_with(
        source.channel_config, {"extra": "param"}
    )


@pytest.mark.asyncio
async def test_collect_propagates_failure():
    source = MagicMock()
    source.channel_type = "api"
    source.channel_config = {}

    error_result = ChannelResult.fail("timeout")
    mock_channel = AsyncMock()
    mock_channel.collect = AsyncMock(return_value=error_result)

    with patch("backend.pipeline.collector.get_channel", return_value=mock_channel):
        result = await collect(source, {})

    assert result.success is False
    assert result.error == "timeout"
