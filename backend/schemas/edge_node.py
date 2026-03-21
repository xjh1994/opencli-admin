from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EdgeNodeRead(BaseModel):
    id: str
    url: str
    label: str
    protocol: str
    mode: str
    node_type: str
    status: str
    last_seen_at: datetime | None
    ip: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EdgeNodeEventRead(BaseModel):
    id: str
    node_id: str
    event: str
    ip: str | None
    event_meta: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}
