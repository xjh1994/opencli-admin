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

    # Relationship
    task: Mapped["CollectionTask"] = relationship("CollectionTask", back_populates="runs")
