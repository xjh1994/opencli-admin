from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelResult:
    """Result from a channel collect() call."""

    success: bool
    items: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.items)

    @classmethod
    def ok(cls, items: list[dict[str, Any]], **metadata: Any) -> "ChannelResult":
        return cls(success=True, items=items, metadata=metadata)

    @classmethod
    def fail(cls, error: str) -> "ChannelResult":
        return cls(success=False, error=error)


class AbstractChannel(ABC):
    """Base class for all data collection channels."""

    channel_type: str

    @abstractmethod
    async def collect(
        self, config: dict[str, Any], parameters: dict[str, Any]
    ) -> ChannelResult:
        """Collect data from the channel.

        Args:
            config: Channel-specific configuration (from DataSource.channel_config).
            parameters: Runtime parameters (e.g., from task trigger).

        Returns:
            ChannelResult with collected items or error.
        """

    @abstractmethod
    async def validate_config(self, config: dict[str, Any]) -> list[str]:
        """Validate config dict; return list of error strings (empty = valid)."""

    async def health_check(self) -> bool:
        """Optional health check. Override to implement channel-specific check."""
        return True
