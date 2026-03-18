"""Unit tests for the pipeline normalizer."""

import pytest

from backend.pipeline.normalizer import normalize_item, normalize_items


def test_normalize_item_standard_fields():
    raw = {
        "title": "Test Article",
        "url": "https://example.com/article",
        "content": "Article body text",
        "author": "Alice",
        "published": "2024-01-15",
    }
    normalized, content_hash = normalize_item(raw, "source-123")
    assert normalized["title"] == "Test Article"
    assert normalized["url"] == "https://example.com/article"
    assert normalized["content"] == "Article body text"
    assert normalized["author"] == "Alice"
    assert normalized["published_at"] == "2024-01-15"
    assert normalized["source_id"] == "source-123"
    assert len(content_hash) == 64  # SHA-256 hex


def test_normalize_item_alternate_keys():
    raw = {"headline": "Breaking News", "link": "https://news.com/1", "body": "Full text"}
    normalized, _ = normalize_item(raw, "src")
    assert normalized["title"] == "Breaking News"
    assert normalized["url"] == "https://news.com/1"
    assert normalized["content"] == "Full text"


def test_normalize_item_extra_fields():
    raw = {"title": "Test", "url": "https://ex.com", "custom_score": 42}
    normalized, _ = normalize_item(raw, "src")
    assert normalized.get("extra_custom_score") == 42


def test_normalize_item_dedup_consistency():
    raw = {"title": "Same", "url": "https://ex.com", "content": "text"}
    _, hash1 = normalize_item(raw, "src1")
    _, hash2 = normalize_item(raw, "src1")
    assert hash1 == hash2


def test_normalize_item_different_sources():
    raw = {"title": "Same", "url": "https://ex.com", "content": "text"}
    _, hash1 = normalize_item(raw, "src1")
    _, hash2 = normalize_item(raw, "src2")
    assert hash1 != hash2


def test_normalize_items_batch():
    items = [
        {"title": "A", "url": "https://a.com"},
        {"title": "B", "url": "https://b.com"},
    ]
    triples = normalize_items(items, "src")
    assert len(triples) == 2
    raw, normalized, content_hash = triples[0]
    assert raw == items[0]
    assert normalized["title"] == "A"
    assert len(content_hash) == 64
