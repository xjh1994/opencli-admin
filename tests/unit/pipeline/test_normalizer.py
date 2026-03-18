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


# ── opencli site-specific field mapping tests ─────────────────────────────────

def test_weibo_word_maps_to_title():
    """weibo hot: uses 'word' as the topic name."""
    raw = {"rank": 1, "word": "福建一鸭子活吞41只小鸡", "hot_value": 126652, "category": "民生新闻", "url": "https://s.weibo.com/..."}
    normalized, _ = normalize_item(raw, "weibo-src")
    assert normalized["title"] == "福建一鸭子活吞41只小鸡"
    assert "extra_hot_value" in normalized
    assert "extra_category" in normalized
    # 'word' should not appear as extra_ since it maps to title
    assert "extra_word" not in normalized


def test_twitter_trending_topic_maps_to_title():
    """twitter trending: uses 'topic' as the trend name."""
    raw = {"rank": 1, "topic": "OpenAI", "tweets": "150K"}
    normalized, _ = normalize_item(raw, "twitter-src")
    assert normalized["title"] == "OpenAI"
    assert "extra_tweets" in normalized
    assert "extra_topic" not in normalized


def test_youtube_channel_maps_to_author():
    """youtube search: uses 'channel' as the uploader."""
    raw = {"rank": 1, "title": "Python Tutorial", "channel": "TechChannel", "views": "1.2M", "duration": "15:30", "url": "https://youtube.com/..."}
    normalized, _ = normalize_item(raw, "yt-src")
    assert normalized["author"] == "TechChannel"
    assert "extra_channel" not in normalized


def test_linkedin_listed_maps_to_published_at():
    """linkedin search: uses 'listed' as the posting date."""
    raw = {"rank": 1, "title": "AI Engineer", "company": "ACME", "location": "Remote", "listed": "2 days ago", "salary": "$150K", "url": "https://linkedin.com/..."}
    normalized, _ = normalize_item(raw, "li-src")
    assert normalized["published_at"] == "2 days ago"
    assert "extra_listed" not in normalized


def test_xueqiu_text_maps_to_content():
    """xueqiu feed: uses 'text' as post content (no title)."""
    raw = {"rank": 1, "author": "某投资者", "text": "今日大盘分析...", "likes": 42, "url": "https://xueqiu.com/..."}
    normalized, _ = normalize_item(raw, "xueqiu-src")
    assert normalized["content"] == "今日大盘分析..."
    assert normalized["author"] == "某投资者"
    assert "extra_text" not in normalized


def test_case_insensitive_standard_keys_not_duplicated():
    """Fields matched by standard keys should not appear as extra_* regardless of case."""
    raw = {"Title": "Some Article", "URL": "https://example.com", "Author": "Bob"}
    normalized, _ = normalize_item(raw, "src")
    assert normalized["title"] == "Some Article"
    assert normalized["url"] == "https://example.com"
    assert normalized["author"] == "Bob"
    assert "extra_Title" not in normalized
    assert "extra_URL" not in normalized
    assert "extra_Author" not in normalized


def test_fallback_hash_for_empty_standard_fields():
    """When title/url/content all empty, hash should use full raw data."""
    raw1 = {"rank": 1, "word": "topic A", "hot_value": 1000}
    raw2 = {"rank": 1, "word": "topic B", "hot_value": 2000}
    # Both have 'word' which maps to title, so fallback won't trigger
    _, hash1 = normalize_item(raw1, "src")
    _, hash2 = normalize_item(raw2, "src")
    assert hash1 != hash2


def test_no_standard_fields_uses_raw_hash():
    """Records with no recognizable standard fields get hash from raw data."""
    raw1 = {"metric_a": 100, "metric_b": "foo"}
    raw2 = {"metric_a": 200, "metric_b": "bar"}
    _, hash1 = normalize_item(raw1, "src")
    _, hash2 = normalize_item(raw2, "src")
    assert hash1 != hash2
