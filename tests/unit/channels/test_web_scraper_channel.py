"""Unit tests for the web scraper channel."""

import pytest
from bs4 import BeautifulSoup

from backend.channels.web_scraper_channel import WebScraperChannel


@pytest.fixture
def channel():
    return WebScraperChannel()


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
