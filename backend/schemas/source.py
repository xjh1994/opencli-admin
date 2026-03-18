from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from backend.schemas.common import UTCModel


ChannelType = Literal["opencli", "web_scraper", "api", "rss", "cli"]


class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    channel_type: ChannelType
    channel_config: dict[str, Any] = Field(default_factory=dict)
    ai_config: Optional[dict[str, Any]] = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)


class DataSourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    channel_config: Optional[dict[str, Any]] = None
    ai_config: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None
    tags: Optional[list[str]] = None


class DataSourceRead(UTCModel):
    id: str
    name: str
    description: Optional[str]
    channel_type: str
    channel_config: dict[str, Any]
    ai_config: Optional[dict[str, Any]]
    enabled: bool
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataSourceDetail(DataSourceRead):
    """Extended read with connectivity status."""
    connectivity_ok: Optional[bool] = None
    connectivity_errors: list[str] = Field(default_factory=list)
