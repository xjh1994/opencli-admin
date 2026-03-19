from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from backend.schemas.common import UTCModel


class ModelProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    provider_type: str = "openai"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_model: Optional[str] = None
    notes: Optional[str] = None
    enabled: bool = True


class ModelProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_model: Optional[str] = None
    notes: Optional[str] = None
    enabled: Optional[bool] = None


class ModelProviderRead(UTCModel):
    id: str
    name: str
    provider_type: str
    base_url: Optional[str]
    api_key: Optional[str]
    default_model: Optional[str]
    notes: Optional[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
