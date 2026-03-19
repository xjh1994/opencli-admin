from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TimestampMixin


class ModelProvider(TimestampMixin):
    """Saved AI model provider configuration (credentials + endpoint)."""

    __tablename__ = "model_providers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # claude | openai | local
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False, default="openai")
    base_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
