from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import TimestampMixin

if TYPE_CHECKING:
    from backend.models.source import DataSource
    from backend.models.record import CollectedRecord


class CollectionTask(TimestampMixin):
    """A collection task tied to a data source."""

    __tablename__ = "collection_tasks"

    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True
    )
    # manual | scheduled | webhook
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)  # 1-10
    # pending | running | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    source: Mapped["DataSource"] = relationship("DataSource", back_populates="tasks")
    runs: Mapped[list["TaskRun"]] = relationship(
        "TaskRun", back_populates="task", cascade="all, delete-orphan"
    )
    records: Mapped[list["CollectedRecord"]] = relationship(
        "CollectedRecord", back_populates="task", cascade="all, delete-orphan"
    )


class TaskRun(TimestampMixin):
    """A single execution attempt of a CollectionTask."""

    __tablename__ = "task_runs"

    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collection_tasks.id", ondelete="CASCADE"), nullable=False
    )
    # running | completed | failed
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    worker_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    records_collected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # URL of the edge node that executed this run (set when dispatched to a remote agent)
    node_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Relationship
    task: Mapped["CollectionTask"] = relationship("CollectionTask", back_populates="runs")
    events: Mapped[list["TaskRunEvent"]] = relationship(
        "TaskRunEvent", back_populates="run", cascade="all, delete-orphan",
        order_by="TaskRunEvent.created_at"
    )


class TaskRunEvent(TimestampMixin):
    """A single structured log event for a TaskRun execution trace."""

    __tablename__ = "task_run_events"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # info | warning | error
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    # trigger | collect | normalize | store | ai_process | notify | complete | failed
    step: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    elapsed_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    run: Mapped["TaskRun"] = relationship("TaskRun", back_populates="events")
