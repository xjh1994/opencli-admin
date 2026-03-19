from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TimestampMixin


class BrowserBinding(TimestampMixin):
    """Maps an opencli site to a specific Chrome CDP endpoint."""

    __tablename__ = "browser_bindings"
    __table_args__ = (UniqueConstraint("site", name="uq_browser_bindings_site"),)

    browser_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    site: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
