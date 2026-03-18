from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TimestampMixin


class WorkerNode(TimestampMixin):
    """Tracks registered Celery worker nodes."""

    __tablename__ = "worker_nodes"

    worker_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    # online | offline | busy
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="online")
    active_tasks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
