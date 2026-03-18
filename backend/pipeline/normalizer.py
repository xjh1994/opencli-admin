"""Pipeline Step 2: Normalize raw items to a standard schema."""

import hashlib
import json
from typing import Any

_TITLE_KEYS = ("title", "name", "headline", "subject", "word", "keyword", "topic", "tag")
_URL_KEYS = ("url", "link", "href", "permalink")
_CONTENT_KEYS = ("content", "body", "text", "summary", "description")
_AUTHOR_KEYS = ("author", "creator", "user", "by")
_DATE_KEYS = ("published", "published_at", "date", "created_at", "timestamp")


def _first(item: dict, keys: tuple[str, ...]) -> str:
    lower_map = {k.lower(): v for k, v in item.items()}
    for key in keys:
        val = lower_map.get(key.lower())
        if val and isinstance(val, str):
            return val
    return ""


def normalize_item(raw: dict[str, Any], source_id: str) -> tuple[dict[str, Any], str]:
    """Return (normalized_data, content_hash)."""
    normalized = {
        "title": _first(raw, _TITLE_KEYS),
        "url": _first(raw, _URL_KEYS),
        "content": _first(raw, _CONTENT_KEYS),
        "author": _first(raw, _AUTHOR_KEYS),
        "published_at": _first(raw, _DATE_KEYS),
        "source_id": source_id,
    }
    # Carry over any extra fields not captured above
    standard_keys = {*_TITLE_KEYS, *_URL_KEYS, *_CONTENT_KEYS, *_AUTHOR_KEYS, *_DATE_KEYS}
    for k, v in raw.items():
        if k not in standard_keys:
            normalized[f"extra_{k}"] = v

    # Build dedup hash from stable content; fall back to full raw_data
    # when standard fields are all empty (e.g. site-specific key names)
    title_url_content = normalized["title"] + normalized["url"] + normalized["content"]
    if title_url_content:
        dedup_str = "|".join(
            [normalized["title"], normalized["url"], normalized["content"], source_id]
        )
    else:
        dedup_str = source_id + "|" + json.dumps(raw, sort_keys=True, ensure_ascii=False)
    content_hash = hashlib.sha256(dedup_str.encode()).hexdigest()

    return normalized, content_hash


def normalize_items(
    raw_items: list[dict[str, Any]], source_id: str
) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
    """Return list of (raw, normalized, hash) tuples."""
    return [
        (raw, *normalize_item(raw, source_id))
        for raw in raw_items
    ]
