"""Pipeline orchestrator: collect → normalize → store → [ai] → [notify]."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.source import DataSource
from backend.pipeline import ai_processor, collector, notifier_dispatch, normalizer, storer

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
    session: AsyncSession,
    source: DataSource,
    task_id: str,
    parameters: dict[str, Any] | None = None,
    enable_ai: bool = True,
    enable_notifications: bool = True,
    agent_config: dict[str, Any] | None = None,
) -> PipelineResult:
    """Execute the full collection pipeline for a data source."""
    started = datetime.now(timezone.utc)
    params = parameters or {}

    # Step 1: Collect
    try:
        channel_result = await collector.collect(source, params)
    except Exception as exc:
        logger.exception("Collection failed for source %s", source.id)
        return PipelineResult(success=False, source_id=source.id, error=str(exc))

    if not channel_result.success:
        return PipelineResult(
            success=False, source_id=source.id, error=channel_result.error
        )

    # Step 2: Normalize
    triples = normalizer.normalize_items(channel_result.items, source.id)

    # Step 3: Store
    try:
        new_records, skipped = await storer.store_records(session, task_id, source.id, triples)
    except Exception as exc:
        logger.exception("Storage failed for source %s", source.id)
        await session.rollback()
        return PipelineResult(
            success=False,
            source_id=source.id,
            collected=channel_result.count,
            error=str(exc),
        )

    # Step 4: AI processing (optional)
    # agent_config takes precedence over source.ai_config
    effective_ai_config = agent_config or source.ai_config
    ai_count = 0
    if enable_ai and effective_ai_config and new_records:
        try:
            await ai_processor.process_with_ai(new_records, effective_ai_config)
            ai_count = len(new_records)
        except Exception as exc:
            logger.warning("AI processing failed: %s", exc)

    # Step 5: Notify (optional)
    if enable_notifications and new_records:
        try:
            await notifier_dispatch.dispatch_notifications(session, source.id, new_records)
        except Exception as exc:
            logger.warning("Notification dispatch failed: %s", exc)

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
