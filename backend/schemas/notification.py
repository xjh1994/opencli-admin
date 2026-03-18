from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from backend.schemas.common import UTCModel


class NotificationRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source_id: Optional[str] = None
    trigger_event: str
    notifier_type: str
    notifier_config: dict[str, Any] = Field(default_factory=dict)
    filter_conditions: Optional[dict[str, Any]] = None
    enabled: bool = True


class NotificationRuleUpdate(BaseModel):
    name: Optional[str] = None
    trigger_event: Optional[str] = None
    notifier_type: Optional[str] = None
    notifier_config: Optional[dict[str, Any]] = None
    filter_conditions: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None


class NotificationRuleRead(UTCModel):
    id: str
    name: str
    source_id: Optional[str]
    trigger_event: str
    notifier_type: str
    notifier_config: dict[str, Any]
    filter_conditions: Optional[dict[str, Any]]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationLogRead(UTCModel):
    id: str
    rule_id: str
    record_id: Optional[str]
    status: str
    response_data: Optional[dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
