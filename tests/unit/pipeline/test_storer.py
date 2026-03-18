"""Unit tests for pipeline storer."""

import pytest

from backend.pipeline.storer import store_records


@pytest.mark.asyncio
async def test_store_new_records(db_session):
    from backend.models.source import DataSource
    from backend.models.task import CollectionTask

    # Create source and task for FK constraints
    source = DataSource(
        name="Test Source",
        channel_type="rss",
        channel_config={"feed_url": "https://example.com/feed.xml"},
    )
    db_session.add(source)
    await db_session.flush()

    task = CollectionTask(source_id=source.id, trigger_type="manual", parameters={})
    db_session.add(task)
    await db_session.flush()

    triples = [
        (
            {"title": "Article 1"},
            {"title": "Article 1", "url": "", "content": "", "author": "", "published_at": "", "source_id": source.id},
            "hash_abc123_1",
        ),
        (
            {"title": "Article 2"},
            {"title": "Article 2", "url": "", "content": "", "author": "", "published_at": "", "source_id": source.id},
            "hash_abc123_2",
        ),
    ]

    new_records, skipped = await store_records(db_session, task.id, source.id, triples)
    assert len(new_records) == 2
    assert skipped == 0


@pytest.mark.asyncio
async def test_store_deduplication(db_session):
    from backend.models.source import DataSource
    from backend.models.task import CollectionTask

    source = DataSource(
        name="Dedup Source",
        channel_type="rss",
        channel_config={"feed_url": "https://example.com/feed.xml"},
    )
    db_session.add(source)
    await db_session.flush()

    task = CollectionTask(source_id=source.id, trigger_type="manual", parameters={})
    db_session.add(task)
    await db_session.flush()

    triple = (
        {"title": "Same Article"},
        {"title": "Same", "url": "", "content": "", "author": "", "published_at": "", "source_id": source.id},
        "same_hash_xyz",
    )

    # First store: new record
    records1, skipped1 = await store_records(db_session, task.id, source.id, [triple])
    assert len(records1) == 1
    assert skipped1 == 0

    # Second store: duplicate should be skipped
    records2, skipped2 = await store_records(db_session, task.id, source.id, [triple])
    assert len(records2) == 0
    assert skipped2 == 1


@pytest.mark.asyncio
async def test_store_empty_input(db_session):
    new_records, skipped = await store_records(db_session, "task-id", "src-id", [])
    assert new_records == []
    assert skipped == 0
