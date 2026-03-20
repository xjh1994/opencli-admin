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


class BrowserInstance(TimestampMixin):
    """Metadata for each Chrome pool instance (mode, label, node_type)."""

    __tablename__ = "browser_instances"

    endpoint: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # "bridge" → opencli 1.0.0 via daemon+extension
    # "cdp"    → opencli 0.9.6 via Playwright direct CDP
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="bridge")
    label: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    # "local"  → Chrome runs on same host / docker network as API (current default)
    # "agent"  → Chrome runs on a remote edge node; agent connects back to center
    node_type: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
