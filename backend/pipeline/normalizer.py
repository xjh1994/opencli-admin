"""Pipeline Step 2: Normalize raw items to a standard schema."""

import hashlib
import json
from typing import Any

# Field name aliases per semantic meaning, ordered by priority.
# Covers all known opencli site output fields.
_TITLE_KEYS = (
    "title",     # most sites
    "name",      # barchart, boss, ctrip, xueqiu hot-stock
    "word",      # weibo hot
    "topic",     # twitter trending
    "headline",  # generic
    "subject",   # generic email-style
)
_URL_KEYS = ("url", "link", "href", "permalink")
_CONTENT_KEYS = (
    "content",      # bilibili subtitle, reddit read
    "text",         # twitter timeline/search, xueqiu feed, bilibili dynamic
    "body",         # generic
    "summary",      # generic
    "description",  # bbc, boss, barchart, xiaoyuzhou podcast
)
_AUTHOR_KEYS = (
    "author",   # most sites
    "channel",  # youtube
    "creator",  # generic
    "by",       # hackernews raw API (yaml maps to author, but keep as fallback)
    "user",     # generic
)
_DATE_KEYS = (
    "created_at",   # twitter, bilibili
    "published_at", # generic
    "published",    # generic RSS
    "date",         # reuters
    "time",         # v2ex notifications
    "listed",       # linkedin
    "updated",      # xiaoyuzhou podcast
    "timestamp",    # generic
)

# All known standard field names (lowercase) — used to decide what goes into extra_*
_STANDARD_KEYS_LOWER: frozenset[str] = frozenset(
    k.lower()
    for keys in (_TITLE_KEYS, _URL_KEYS, _CONTENT_KEYS, _AUTHOR_KEYS, _DATE_KEYS)
    for k in keys
)


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
    # Carry over any extra fields not captured above (case-insensitive exclusion)
    for k, v in raw.items():
        if k.lower() not in _STANDARD_KEYS_LOWER:
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
