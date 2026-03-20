from datetime import datetime

from pydantic import BaseModel


class BrowserBindingCreate(BaseModel):
    browser_endpoint: str
    site: str
    notes: str | None = None


class BrowserBindingRead(BaseModel):
    id: str
    browser_endpoint: str
    site: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrowserInstanceRead(BaseModel):
    id: str
    endpoint: str
    mode: str
    node_type: str
    agent_url: str | None
    label: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
