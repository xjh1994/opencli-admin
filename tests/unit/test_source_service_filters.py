"""Tests for source service filter paths."""

import pytest

from backend.models.source import DataSource
from backend.services import source_service


@pytest.mark.asyncio
async def test_list_sources_filter_by_enabled(db_session):
    db_session.add(DataSource(
        name="Enabled", channel_type="rss",
        channel_config={"feed_url": "https://a.com"}, enabled=True
    ))
    db_session.add(DataSource(
        name="Disabled", channel_type="rss",
        channel_config={"feed_url": "https://b.com"}, enabled=False
    ))
    await db_session.flush()

    enabled, total = await source_service.list_sources(db_session, enabled=True)
    assert total == 1
    assert enabled[0].name == "Enabled"


@pytest.mark.asyncio
async def test_list_sources_filter_by_channel_type(db_session):
    db_session.add(DataSource(
        name="RSS Source", channel_type="rss",
        channel_config={"feed_url": "https://a.com"}
    ))
    db_session.add(DataSource(
        name="API Source", channel_type="api",
        channel_config={"base_url": "https://api.com", "endpoint": "/data"}
    ))
    await db_session.flush()

    rss_sources, total = await source_service.list_sources(db_session, channel_type="rss")
    assert total == 1
    assert rss_sources[0].name == "RSS Source"


@pytest.mark.asyncio
async def test_validate_source_config_invalid_channel_type(db_session):
    source = DataSource(
        name="Bad Type",
        channel_type="nonexistent_type",
        channel_config={},
    )
    errors = await source_service.validate_source_config(source)
    assert len(errors) > 0


@pytest.mark.asyncio
async def test_test_source_connectivity_with_config_errors(db_session):
    # RSS source with missing feed_url — config validation fails
    source = DataSource(
        name="No URL",
        channel_type="rss",
        channel_config={},  # Missing feed_url
    )
    ok, errors = await source_service.test_source_connectivity(source)
    assert ok is False
    assert len(errors) > 0
