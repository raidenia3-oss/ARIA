from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    ON_TIME = "on_time"
    ON_EVENT = "on_event"
    ON_CONDITION = "on_condition"
    ON_STARTUP = "on_startup"


class ActionType(str, Enum):
    SKILL = "skill"
    CHAT = "chat"
    API_CALL = "api_call"
    DELAY = "delay"
    NOTIFICATION = "notification"


class Action(BaseModel):
    type: ActionType
    params: Dict[str, Any] = Field(default_factory=dict)
    skill: Optional[str] = None
    message: Optional[str] = None
    method: Optional[str] = "POST"
    url: Optional[str] = None
    seconds: Optional[float] = None
    title: Optional[str] = None
    body: Optional[str] = None


class Trigger(BaseModel):
    type: TriggerType
    params: Dict[str, Any] = Field(default_factory=dict)
    hour: Optional[int] = None
    minute: Optional[int] = None
    days: Optional[List[str]] = None
    event: Optional[str] = None
    skill: Optional[str] = None
    condition: Optional[str] = None


class AutomationRuleModel(BaseModel):
    name: str
    description: Optional[str] = None
    trigger: Trigger
    actions: List[Action]
    enabled: bool = True
    tags: List[str] = Field(default_factory=list)
