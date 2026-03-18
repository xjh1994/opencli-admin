from typing import Optional

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import TimestampMixin


class NotificationRule(TimestampMixin):
    """Defines when and how to send notifications."""

    __tablename__ = "notification_rules"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Source filter: null means all sources
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True
    )
    # Trigger: on_new_record | on_ai_processed | on_task_failed
    trigger_event: Mapped[str] = mapped_column(String(50), nullable=False)
    # webhook | email | feishu | dingtalk | wecom
    notifier_type: Mapped[str] = mapped_column(String(50), nullable=False)
    notifier_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Optional filter conditions as JSON logic
    filter_conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    logs: Mapped[list["NotificationLog"]] = relationship(
        "NotificationLog", back_populates="rule", cascade="all, delete-orphan"
    )


class NotificationLog(TimestampMixin):
    """Log of each notification attempt."""

    __tablename__ = "notification_logs"

    rule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notification_rules.id", ondelete="CASCADE"), nullable=False
    )
    record_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # sent | failed
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    response_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rule: Mapped["NotificationRule"] = relationship("NotificationRule", back_populates="logs")
