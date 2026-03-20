"""Unit tests for the RSS channel."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.channels.rss_channel import RSSChannel


@pytest.fixture
def channel():
    return RSSChannel()


VALID_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Item 1</title>
      <link>https://ex.com/1</link>
      <description>Desc 1</description>
    </item>
    <item>
      <title>Item 2</title>
      <link>https://ex.com/2</link>
    </item>
  </channel>
</rss>"""


# ── validate_config ────────────────────────────────────────────────────────────

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


# ── collect: success ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_success_returns_items(channel):
    """Successful RSS fetch returns ChannelResult with parsed items."""
    mock_response = MagicMock()
    mock_response.text = VALID_RSS_XML
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {"feed_url": "https://example.com/rss"}, {}
        )

    assert result.success is True
    assert len(result.items) == 2
    assert result.items[0]["title"] == "Item 1"
    assert result.items[0]["link"] == "https://ex.com/1"


@pytest.mark.asyncio
async def test_collect_max_entries_limits_results(channel):
    """max_entries config option trims entries."""
    mock_response = MagicMock()
    mock_response.text = VALID_RSS_XML
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {"feed_url": "https://example.com/rss", "max_entries": 1}, {}
        )

    assert result.success is True
    assert len(result.items) == 1


@pytest.mark.asyncio
async def test_collect_metadata_includes_feed_title(channel):
    """ChannelResult metadata contains the feed title."""
    mock_response = MagicMock()
    mock_response.text = VALID_RSS_XML
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {"feed_url": "https://example.com/rss"}, {}
        )

    assert result.success is True
    assert result.metadata.get("feed_title") == "Test Feed"


# ── collect: error cases ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_timeout_returns_fail(channel):
    """TimeoutException should produce a failed ChannelResult."""
    import httpx

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {"feed_url": "https://example.com/rss"}, {}
        )

    assert result.success is False
    assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_collect_http_404_returns_fail(channel):
    """HTTP 404 status should produce a failed ChannelResult."""
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            message="Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )
    )
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {"feed_url": "https://example.com/rss"}, {}
        )

    assert result.success is False
    assert "404" in result.error


@pytest.mark.asyncio
async def test_collect_generic_exception_returns_fail(channel):
    """Any other request exception should produce a failed ChannelResult."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=ConnectionError("network down"))
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {"feed_url": "https://example.com/rss"}, {}
        )

    assert result.success is False
    assert "Failed to fetch" in result.error


@pytest.mark.asyncio
async def test_collect_bozo_feed_no_entries_returns_fail(channel):
    """A bozo (broken) feed with no entries should return a failed ChannelResult."""
    mock_response = MagicMock()
    mock_response.text = "NOT VALID XML AT ALL !!!"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    # Force feedparser to report bozo with no entries
    fake_parsed = MagicMock()
    fake_parsed.bozo = True
    fake_parsed.entries = []

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        with patch("feedparser.parse", return_value=fake_parsed):
            result = await channel.collect(
                {"feed_url": "https://example.com/rss"}, {}
            )

    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_collect_bozo_feed_with_entries_succeeds(channel):
    """A bozo feed that still has entries should succeed (feedparser partial parse)."""
    mock_response = MagicMock()
    mock_response.text = VALID_RSS_XML
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    fake_entry = MagicMock()
    fake_entry.get = lambda k, default="": {
        "title": "Partial Item",
        "link": "https://ex.com/p",
        "summary": "",
        "author": "",
        "published": "",
        "id": "pid1",
        "tags": [],
    }.get(k, default)

    fake_parsed = MagicMock()
    fake_parsed.bozo = True
    fake_parsed.entries = [fake_entry]
    fake_parsed.feed = MagicMock()
    fake_parsed.feed.get = lambda k, default="": default

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        with patch("feedparser.parse", return_value=fake_parsed):
            result = await channel.collect(
                {"feed_url": "https://example.com/rss"}, {}
            )

    assert result.success is True
    assert len(result.items) == 1


# ── _entry_to_dict ─────────────────────────────────────────────────────────────

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


def test_entry_to_dict_missing_optional_fields(channel):
    """Entry with only link should use link as id fallback."""
    class MinimalEntry:
        def get(self, key, default=""):
            return {"link": "https://ex.com/x"}.get(key, default)

    result = channel._entry_to_dict(MinimalEntry())
    assert result["link"] == "https://ex.com/x"
    assert result["id"] == "https://ex.com/x"
    assert result["tags"] == []


def test_entry_to_dict_all_tags(channel):
    """Multiple tags are all extracted."""
    class TaggedEntry:
        def get(self, key, default=""):
            return {"tags": [{"term": "a"}, {"term": "b"}, {"term": "c"}]}.get(key, default)

    result = channel._entry_to_dict(TaggedEntry())
    assert result["tags"] == ["a", "b", "c"]
