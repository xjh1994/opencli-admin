"""Web scraper channel using httpx + BeautifulSoup."""

from typing import Any

import httpx
from bs4 import BeautifulSoup

from backend.channels.base import AbstractChannel, ChannelResult
from backend.channels.registry import register_channel


@register_channel
class WebScraperChannel(AbstractChannel):
    """Collect data by scraping web pages with CSS selectors."""

    channel_type = "web_scraper"

    async def collect(
        self, config: dict[str, Any], parameters: dict[str, Any]
    ) -> ChannelResult:
        url: str = config.get("url", "")
        selectors: dict[str, str] = config.get("selectors", {})
        headers: dict[str, str] = config.get("headers", {})
        timeout: int = config.get("timeout", 30)
        list_selector: str = config.get("list_selector", "")

        merged_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; opencli-admin/1.0)",
            **headers,
        }

        try:
            async with httpx.AsyncClient(
                headers=merged_headers, follow_redirects=True, timeout=timeout
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.TimeoutException:
            return ChannelResult.fail(f"Request to {url} timed out after {timeout}s")
        except httpx.HTTPStatusError as exc:
            return ChannelResult.fail(f"HTTP {exc.response.status_code} from {url}")
        except Exception as exc:
            return ChannelResult.fail(f"Request failed: {exc}")

        soup = BeautifulSoup(response.text, "lxml")

        if list_selector:
            containers = soup.select(list_selector)
            items = [
                self._extract_fields(container, selectors) for container in containers
            ]
        else:
            items = [self._extract_fields(soup, selectors)]

        return ChannelResult.ok(items, url=url, status_code=response.status_code)

    def _extract_fields(self, node: Any, selectors: dict[str, str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field_name, selector in selectors.items():
            el = node.select_one(selector)
            if el is not None:
                result[field_name] = el.get_text(strip=True)
        return result

    async def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not config.get("url"):
            errors.append("'url' is required for web_scraper channel")
        if not config.get("selectors"):
            errors.append("'selectors' is required for web_scraper channel")
        return errors
