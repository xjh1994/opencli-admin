"""Pipeline Step 1: Dispatch to the appropriate channel."""

from typing import Any

from backend.channels.base import ChannelResult
from backend.channels.registry import get_channel
from backend.models.source import DataSource


async def collect(source: DataSource, parameters: dict[str, Any]) -> ChannelResult:
    """Dispatch collection to the registered channel for the given source."""
    channel = get_channel(source.channel_type)
    return await channel.collect(source.channel_config, parameters)
