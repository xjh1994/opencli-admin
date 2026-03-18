"""Unit tests for the RSS channel."""

import pytest

from backend.channels.rss_channel import RSSChannel


@pytest.fixture
def channel():
    return RSSChannel()


@pytest.mark.asyncio
async def test_channel_type(channel):
    assert channel.channel_type == "rss"


@pytest.mark.asyncio
async def test_validate_config_missing_feed_url(channel):
    errors = await channel.validate_config({})
    assert any("feed_url" in e for e in errors)


@pytest.mark.asyncio
async def test_validate_config_valid(channel):
    errors = await channel.validate_config({"feed_url": "https://example.com/rss"})
    assert errors == []


@pytest.mark.asyncio
async def test_entry_to_dict(channel):
    class FakeEntry:
        def get(self, key, default=""):
            data = {
                "title": "Test Title",
                "link": "https://example.com/post",
                "summary": "A summary",
                "author": "Alice",
                "published": "2024-01-01",
                "tags": [{"term": "python"}],
                "id": "abc123",
            }
            return data.get(key, default)

    result = channel._entry_to_dict(FakeEntry())
    assert result["title"] == "Test Title"
    assert result["link"] == "https://example.com/post"
    assert "python" in result["tags"]
