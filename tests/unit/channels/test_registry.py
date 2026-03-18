"""Unit tests for the channel registry."""

import pytest

from backend.channels.registry import get_channel, list_channel_types


def test_all_channels_registered():
    types = list_channel_types()
    assert "opencli" in types
    assert "web_scraper" in types
    assert "api" in types
    assert "rss" in types
    assert "cli" in types


def test_get_channel_valid():
    channel = get_channel("rss")
    assert channel.channel_type == "rss"


def test_get_channel_invalid():
    with pytest.raises(ValueError, match="Unknown channel type"):
        get_channel("nonexistent_channel_type")
