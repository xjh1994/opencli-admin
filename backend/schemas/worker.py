from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from backend.schemas.common import UTCModel


class WorkerNodeRead(UTCModel):
    id: str
    worker_id: str
    hostname: str
    status: str
    active_tasks: int
    last_heartbeat: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
