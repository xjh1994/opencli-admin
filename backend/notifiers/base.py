from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NotificationPayload:
    event: str
    source_id: str
    record_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    ai_enrichment: dict[str, Any] | None = None


class AbstractNotifier(ABC):
    notifier_type: str

    @abstractmethod
    async def send(self, config: dict[str, Any], payload: NotificationPayload) -> bool: ...
