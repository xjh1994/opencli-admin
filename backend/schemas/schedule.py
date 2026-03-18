from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from backend.schemas.common import UTCModel


class CronScheduleCreate(BaseModel):
    source_id: str
    name: str = Field(..., min_length=1, max_length=255)
    cron_expression: str = Field(..., description="5-field cron expression")
    timezone: str = "UTC"
    parameters: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class CronScheduleUpdate(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    parameters: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None


class CronScheduleRead(UTCModel):
    id: str
    source_id: str
    name: str
    cron_expression: str
    timezone: str
    parameters: dict[str, Any]
    enabled: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
