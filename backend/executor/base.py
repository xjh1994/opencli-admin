from abc import ABC, abstractmethod


class AbstractExecutor(ABC):
    @abstractmethod
    async def dispatch_collection(self, task_id: str, parameters: dict) -> dict: ...

    @abstractmethod
    async def dispatch_scheduled_collection(
        self, schedule_id: str, source_id: str, parameters: dict
    ) -> None: ...
