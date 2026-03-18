from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.schemas.common import UTCModel


class AIAgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    processor_type: str = "claude"
    model: Optional[str] = None
    prompt_template: str = ""
    processor_config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class AIAgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    processor_type: Optional[str] = None
    model: Optional[str] = None
    prompt_template: Optional[str] = None
    processor_config: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None


class AIAgentRead(UTCModel):
    id: str
    name: str
    description: Optional[str]
    processor_type: str
    model: Optional[str]
    prompt_template: str
    processor_config: dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
