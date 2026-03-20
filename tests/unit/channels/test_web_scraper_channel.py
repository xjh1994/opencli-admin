"""Unit tests for the web scraper channel."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from backend.channels.web_scraper_channel import WebScraperChannel


@pytest.fixture
def channel():
    return WebScraperChannel()


SAMPLE_HTML = """
<html>
<body>
  <ul>
    <li class="item">
      <h2 class="title">Item Alpha</h2>
      <span class="price">$10</span>
    </li>
    <li class="item">
      <h2 class="title">Item Beta</h2>
      <span class="price">$20</span>
    </li>
  </ul>
  <h1 class="page-title">Products</h1>
</body>
</html>
"""


def _make_mock_response(status_code=200, text=SAMPLE_HTML):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.raise_for_status = MagicMock()
    return response


def _make_mock_client(response):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_client_ctx


# ── validate_config ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_config_missing_url(channel):
    errors = await channel.validate_config({"selectors": {"title": "h1"}})
    assert any("url" in e for e in errors)


@pytest.mark.asyncio
async def test_validate_config_missing_selectors(channel):
    errors = await channel.validate_config({"url": "https://example.com"})
    assert any("selectors" in e for e in errors)


@pytest.mark.asyncio
async def test_validate_config_valid(channel):
    errors = await channel.validate_config({
        "url": "https://example.com",
        "selectors": {"title": "h1"},
    })
    assert errors == []


@pytest.mark.asyncio
async def test_validate_config_missing_both(channel):
    errors = await channel.validate_config({})
    assert len(errors) == 2


# ── collect: with list_selector ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_with_list_selector(channel):
    """list_selector finds multiple containers and extracts fields from each."""
    response = _make_mock_response()
    mock_client_ctx = _make_mock_client(response)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {
                "url": "https://example.com",
                "list_selector": "li.item",
                "selectors": {"title": "h2.title", "price": "span.price"},
            },
            {},
        )

    assert result.success is True
    assert len(result.items) == 2
    assert result.items[0]["title"] == "Item Alpha"
    assert result.items[0]["price"] == "$10"
    assert result.items[1]["title"] == "Item Beta"
    assert result.items[1]["price"] == "$20"


@pytest.mark.asyncio
async def test_collect_list_selector_no_matches(channel):
    """list_selector with no matches returns empty items list."""
    response = _make_mock_response()
    mock_client_ctx = _make_mock_client(response)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {
                "url": "https://example.com",
                "list_selector": "div.nonexistent",
                "selectors": {"title": "h2"},
            },
            {},
        )

    assert result.success is True
    assert len(result.items) == 0


# ── collect: without list_selector ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_without_list_selector(channel):
    """Without list_selector, extracts a single item from whole page."""
    response = _make_mock_response()
    mock_client_ctx = _make_mock_client(response)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {
                "url": "https://example.com",
                "selectors": {"page_title": "h1.page-title"},
            },
            {},
        )

    assert result.success is True
    assert len(result.items) == 1
    assert result.items[0]["page_title"] == "Products"


@pytest.mark.asyncio
async def test_collect_metadata_includes_url_and_status(channel):
    """ChannelResult metadata contains url and status_code."""
    response = _make_mock_response()
    mock_client_ctx = _make_mock_client(response)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {
                "url": "https://example.com",
                "selectors": {"title": "h1"},
            },
            {},
        )

    assert result.success is True
    assert result.metadata.get("url") == "https://example.com"
    assert result.metadata.get("status_code") == 200


# ── collect: error cases ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_timeout_returns_fail(channel):
    """TimeoutException produces a failed ChannelResult."""
    import httpx

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {"url": "https://example.com", "selectors": {"title": "h1"}}, {}
        )

    assert result.success is False
    assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_collect_http_error_returns_fail(channel):
    """HTTP 403 status produces a failed ChannelResult."""
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            message="Forbidden",
            request=MagicMock(),
            response=MagicMock(status_code=403),
        )
    )
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {"url": "https://example.com", "selectors": {"title": "h1"}}, {}
        )

    assert result.success is False
    assert "403" in result.error


@pytest.mark.asyncio
async def test_collect_generic_exception_returns_fail(channel):
    """Connection errors produce a failed ChannelResult."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=OSError("connection refused"))
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_ctx):
        result = await channel.collect(
            {"url": "https://example.com", "selectors": {"title": "h1"}}, {}
        )

    assert result.success is False
    assert "Request failed" in result.error


# ── _extract_fields ────────────────────────────────────────────────────────────

def test_extract_fields(channel):
    html = "<html><body><h1>Hello World</h1><p class='desc'>Description</p></body></html>"
    soup = BeautifulSoup(html, "lxml")
    selectors = {"title": "h1", "description": "p.desc"}
    result = channel._extract_fields(soup, selectors)
    assert result["title"] == "Hello World"
    assert result["description"] == "Description"


def test_extract_fields_missing_selector(channel):
    html = "<html><body><h1>Hello</h1></body></html>"
    soup = BeautifulSoup(html, "lxml")
    result = channel._extract_fields(soup, {"title": "h1", "missing": ".no-exist"})
    assert result["title"] == "Hello"
    assert "missing" not in result


def test_extract_fields_empty_selectors(channel):
    html = "<html><body><h1>Hello</h1></body></html>"
    soup = BeautifulSoup(html, "lxml")
    result = channel._extract_fields(soup, {})
    assert result == {}


def test_extract_fields_strips_whitespace(channel):
    html = "<html><body><p class='p'>  spaced text  </p></body></html>"
    soup = BeautifulSoup(html, "lxml")
    result = channel._extract_fields(soup, {"text": "p.p"})
    assert result["text"] == "spaced text"


@pytest.mark.asyncio
async def test_collect_custom_headers_sent(channel):
    """Custom headers from config are merged with default User-Agent."""
    response = _make_mock_response()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    captured_headers = {}

    def fake_client_constructor(**kwargs):
        captured_headers.update(kwargs.get("headers", {}))
        return mock_client_ctx

    with patch("httpx.AsyncClient", side_effect=fake_client_constructor):
        result = await channel.collect(
            {
                "url": "https://example.com",
                "selectors": {"title": "h1"},
                "headers": {"X-My-Header": "custom-value"},
            },
            {},
        )

    assert result.success is True
    assert captured_headers.get("X-My-Header") == "custom-value"
    assert "User-Agent" in captured_headers
