from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from backend.schemas.common import UTCModel


class TaskTriggerRequest(BaseModel):
    source_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=1, le=10)


class CollectionTaskRead(UTCModel):
    id: str
    source_id: str
    trigger_type: str
    parameters: dict[str, Any]
    priority: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskRunRead(UTCModel):
    id: str
    task_id: str
    status: str
    worker_id: Optional[str]
    celery_task_id: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_ms: Optional[int]
    records_collected: int
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
