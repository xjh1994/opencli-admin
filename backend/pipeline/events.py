"""Pipeline event writer — persists TaskRunEvent rows."""
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def emit(
    run_id: str,
    step: str,
    message: str,
    level: str = "info",
    detail: dict[str, Any] | None = None,
    elapsed_ms: int | None = None,
) -> None:
    """Write a single TaskRunEvent to the database (best-effort, never raises)."""
    try:
        from backend.database import AsyncSessionLocal
        from backend.models.task import TaskRunEvent
        async with AsyncSessionLocal() as session:
            event = TaskRunEvent(
                run_id=run_id,
                level=level,
                step=step,
                message=message,
                detail=detail,
                elapsed_ms=elapsed_ms,
            )
            session.add(event)
            await session.commit()
    except Exception as exc:
        logger.warning("emit event failed: %s", exc)
