"""Pipeline Step 5: Dispatch notifications based on rules."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.notification import NotificationLog, NotificationRule
from backend.models.record import CollectedRecord
from backend.notifiers.base import NotificationPayload
from backend.notifiers.registry import get_notifier


async def dispatch_notifications(
    session: AsyncSession,
    source_id: str,
    records: list[CollectedRecord],
    trigger_event: str = "on_new_record",
) -> None:
    """Find matching notification rules and dispatch."""
    if not records:
        return

    result = await session.execute(
        select(NotificationRule).where(
            NotificationRule.enabled.is_(True),
            NotificationRule.trigger_event == trigger_event,
            (NotificationRule.source_id == source_id)
            | (NotificationRule.source_id.is_(None)),
        )
    )
    rules = result.scalars().all()

    for rule in rules:
        try:
            notifier = get_notifier(rule.notifier_type)
        except ValueError:
            continue

        for record in records:
            payload = NotificationPayload(
                event=trigger_event,
                source_id=source_id,
                record_id=record.id,
                data=record.normalized_data,
                ai_enrichment=record.ai_enrichment,
            )
            try:
                success = await notifier.send(rule.notifier_config, payload)
                status = "sent" if success else "failed"
                error_msg = None
            except Exception as exc:
                status = "failed"
                error_msg = str(exc)

            log = NotificationLog(
                rule_id=rule.id,
                record_id=record.id,
                status=status,
                error_message=error_msg,
            )
            session.add(log)
