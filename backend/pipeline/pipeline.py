"""Pipeline orchestrator: collect → normalize → store → [ai] → [notify]."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.models.source import DataSource

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    success: bool
    source_id: str
    collected: int = 0
    stored: int = 0
    skipped: int = 0
    ai_processed: int = 0
    notifications_sent: int = 0
    error: str | None = None
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


async def run_pipeline(
    task_id: str,
    source: DataSource,
    parameters: dict[str, Any] | None = None,
    enable_ai: bool = True,
    enable_notifications: bool = True,
    agent_config: dict[str, Any] | None = None,
) -> PipelineResult:
    """Execute the full collection pipeline. Each write step uses its own
    short-lived session so no write lock is held during long-running I/O."""
    from backend.database import AsyncSessionLocal
    from backend.pipeline import ai_processor, collector, notifier_dispatch, normalizer, storer

    started = datetime.now(timezone.utc)
    params = parameters or {}

    # Step 1: Collect
    logger.info("[task:%s] step1/collect start | source=%s channel=%s params=%s",
                task_id, source.name, source.channel_type, params)
    try:
        channel_result = await collector.collect(source, params)
    except Exception as exc:
        logger.exception("[task:%s] step1/collect exception | %s", task_id, exc)
        return PipelineResult(success=False, source_id=source.id, error=str(exc))

    if not channel_result.success:
        logger.error("[task:%s] step1/collect failed | error=%s", task_id, channel_result.error)
        return PipelineResult(success=False, source_id=source.id, error=channel_result.error)

    logger.info("[task:%s] step1/collect done | count=%d metadata=%s",
                task_id, channel_result.count, channel_result.metadata)

    # Step 2: Normalize
    triples = normalizer.normalize_items(channel_result.items, source.id)
    logger.info("[task:%s] step2/normalize done | items=%d", task_id, len(triples))

    # Step 3: Store
    logger.info("[task:%s] step3/store start | items=%d", task_id, len(triples))
    try:
        async with AsyncSessionLocal() as session:
            new_records, skipped = await storer.store_records(session, task_id, source.id, triples)
            await session.commit()
    except Exception as exc:
        logger.exception("[task:%s] step3/store exception | %s", task_id, exc)
        return PipelineResult(
            success=False,
            source_id=source.id,
            collected=channel_result.count,
            error=str(exc),
        )
    logger.info("[task:%s] step3/store done | new=%d skipped=%d",
                task_id, len(new_records), skipped)

    # Step 4: AI processing
    effective_ai_config = agent_config or source.ai_config
    ai_count = 0
    if enable_ai and effective_ai_config and new_records:
        processor_type = effective_ai_config.get("processor_type", "claude")
        model = effective_ai_config.get("model", "")
        logger.info("[task:%s] step4/ai start | processor=%s model=%s records=%d",
                    task_id, processor_type, model, len(new_records))

        async with AsyncSessionLocal() as session:
            from backend.models.task import CollectionTask
            task_row = await session.get(CollectionTask, task_id)
            if task_row:
                task_row.status = "ai_processing"
                await session.commit()
        try:
            await ai_processor.process_with_ai(new_records, effective_ai_config)
            ai_count = len(new_records)
            logger.info("[task:%s] step4/ai done | processed=%d", task_id, ai_count)
        except Exception as exc:
            logger.warning("[task:%s] step4/ai failed | %s", task_id, exc)
    elif enable_ai and not effective_ai_config:
        logger.debug("[task:%s] step4/ai skipped | no ai_config", task_id)

    # Step 5: Notify
    if enable_notifications and new_records:
        logger.info("[task:%s] step5/notify start | records=%d", task_id, len(new_records))
        try:
            async with AsyncSessionLocal() as session:
                await notifier_dispatch.dispatch_notifications(session, source.id, new_records)
                await session.commit()
            logger.info("[task:%s] step5/notify done", task_id)
        except Exception as exc:
            logger.warning("[task:%s] step5/notify failed | %s", task_id, exc)

    duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    return PipelineResult(
        success=True,
        source_id=source.id,
        collected=channel_result.count,
        stored=len(new_records),
        skipped=skipped,
        ai_processed=ai_count,
        duration_ms=duration_ms,
        metadata=channel_result.metadata,
    )
