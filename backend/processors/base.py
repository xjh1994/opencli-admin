from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.models.record import CollectedRecord


@dataclass
class ProcessingResult:
    success: bool
    enrichments: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class AbstractProcessor(ABC):
    processor_type: str

    @abstractmethod
    async def process(
        self,
        records: list["CollectedRecord"],
        prompt_template: str,
        config: dict[str, Any],
    ) -> ProcessingResult: ...
