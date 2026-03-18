from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.channels.base import AbstractChannel

_REGISTRY: dict[str, "AbstractChannel"] = {}


def register_channel(cls: type) -> type:
    """Class decorator to register a channel implementation."""
    instance = cls()
    _REGISTRY[instance.channel_type] = instance
    return cls


def get_channel(channel_type: str) -> "AbstractChannel":
    if channel_type not in _REGISTRY:
        raise ValueError(
            f"Unknown channel type: {channel_type!r}. "
            f"Available: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[channel_type]


def list_channel_types() -> list[str]:
    return list(_REGISTRY.keys())


def _load_all_channels() -> None:
    """Import all channel modules to trigger registration."""
    from backend.channels import (  # noqa: F401
        api_channel,
        cli_channel,
        opencli_channel,
        rss_channel,
        web_scraper_channel,
    )


_load_all_channels()
