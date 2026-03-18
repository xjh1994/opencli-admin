from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import TimestampMixin

if TYPE_CHECKING:
    from backend.models.task import CollectionTask


class CollectedRecord(TimestampMixin):
    """A single data record collected from a source."""

    __tablename__ = "collected_records"
    __table_args__ = (UniqueConstraint("source_id", "content_hash", name="uq_source_content"),)

    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collection_tasks.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Raw data as returned by the channel
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Normalized standard fields: title, url, content, author, published_at, ...
    normalized_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # AI-enriched fields: summary, tags, sentiment, ...
    ai_enrichment: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # SHA-256 hash of normalized content for deduplication
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Processing status
    # raw | normalized | ai_processed | notified | error
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="raw")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    task: Mapped["CollectionTask"] = relationship("CollectionTask", back_populates="records")
