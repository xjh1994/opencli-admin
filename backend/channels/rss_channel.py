"""RSS channel using feedparser."""

from typing import Any

import feedparser
import httpx

from backend.channels.base import AbstractChannel, ChannelResult
from backend.channels.registry import register_channel


@register_channel
class RSSChannel(AbstractChannel):
    """Collect entries from RSS/Atom feeds."""

    channel_type = "rss"

    async def collect(
        self, config: dict[str, Any], parameters: dict[str, Any]
    ) -> ChannelResult:
        feed_url: str = config.get("feed_url", "")
        max_entries: int = config.get("max_entries", 50)
        timeout: int = config.get("timeout", 30)

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(
                    feed_url,
                    headers={"User-Agent": "opencli-admin/1.0 (+https://github.com)"},
                )
                response.raise_for_status()
                content = response.text
        except httpx.TimeoutException:
            return ChannelResult.fail(f"RSS feed request timed out: {feed_url}")
        except httpx.HTTPStatusError as exc:
            return ChannelResult.fail(f"HTTP {exc.response.status_code} fetching feed")
        except Exception as exc:
            return ChannelResult.fail(f"Failed to fetch RSS feed: {exc}")

        parsed = feedparser.parse(content)
        if parsed.bozo and not parsed.entries:
            return ChannelResult.fail(
                f"Failed to parse feed: {getattr(parsed, 'bozo_exception', 'unknown error')}"
            )

        entries = parsed.entries[:max_entries]
        items = [self._entry_to_dict(entry) for entry in entries]

        return ChannelResult.ok(
            items,
            feed_title=parsed.feed.get("title", ""),
            total_entries=len(parsed.entries),
        )

    def _entry_to_dict(self, entry: Any) -> dict[str, Any]:
        return {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", ""),
            "author": entry.get("author", ""),
            "published": entry.get("published", ""),
            "tags": [t.get("term", "") for t in entry.get("tags", [])],
            "id": entry.get("id", entry.get("link", "")),
        }

    async def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not config.get("feed_url"):
            errors.append("'feed_url' is required for rss channel")
        return errors
