from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import TimestampMixin

if TYPE_CHECKING:
    from backend.models.task import CollectionTask
    from backend.models.schedule import CronSchedule


class DataSource(TimestampMixin):
    """Represents a data source with channel configuration."""

    __tablename__ = "data_sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Channel type: opencli | web_scraper | api | rss | cli
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False)
    channel_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Optional AI processing config
    ai_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Relationships
    tasks: Mapped[list["CollectionTask"]] = relationship(
        "CollectionTask", back_populates="source", cascade="all, delete-orphan"
    )
    schedules: Mapped[list["CronSchedule"]] = relationship(
        "CronSchedule", back_populates="source", cascade="all, delete-orphan"
    )
