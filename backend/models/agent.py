from typing import Optional

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TimestampMixin


class AIAgent(TimestampMixin):
    """AI agent configuration for processing collected content."""

    __tablename__ = "ai_agents"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # claude | openai | local
    processor_type: Mapped[str] = mapped_column(String(50), nullable=False, default="claude")
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    processor_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Optional: link to a saved ModelProvider for credentials
    provider_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
