"""Local in-process executor — runs pipeline directly via asyncio."""

import asyncio
import logging

from backend.executor.base import AbstractExecutor

logger = logging.getLogger(__name__)


class LocalExecutor(AbstractExecutor):
    async def dispatch_collection(self, task_id: str, parameters: dict) -> dict:
        from backend.pipeline.runner import run_collection_pipeline
        asyncio.create_task(run_collection_pipeline(task_id, parameters))
        return {"task_id": task_id}

    async def dispatch_scheduled_collection(
        self, schedule_id: str, source_id: str, parameters: dict
    ) -> None:
        from backend.pipeline.runner import run_scheduled_pipeline
        asyncio.create_task(run_scheduled_pipeline(schedule_id, source_id, parameters))
