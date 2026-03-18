from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel
from backend.schemas.common import UTCModel


class CollectedRecordRead(UTCModel):
    id: str
    task_id: str
    source_id: str
    raw_data: dict[str, Any]
    normalized_data: dict[str, Any]
    ai_enrichment: Optional[dict[str, Any]]
    content_hash: str
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecordFilter(BaseModel):
    source_id: Optional[str] = None
    task_id: Optional[str] = None
    status: Optional[str] = None
    page: int = 1
    limit: int = 20
