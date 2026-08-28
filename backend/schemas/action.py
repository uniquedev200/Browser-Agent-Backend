from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.config.settings import SUPPORTED_ACTION_TYPES


class ActionType(str, Enum):
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    CHECK = "check"
    UNCHECK = "uncheck"
    SCROLL = "scroll"
    WAIT = "wait"
    PRESS_KEY = "press_key"
    UPLOAD = "upload"
    DONE = "done"


class Action(BaseModel):
    action_id: str
    type: str
    target: Optional[str] = None
    value: Optional[str] = None
    key: Optional[str] = None
    direction: Optional[str] = None
    amount: Optional[int] = None
    selector: Optional[str] = None


class ActionBatch(BaseModel):
    status: str = "continue"
    phase: str = ""
    actions: list[Action] = Field(default_factory=list)
    checkpoint: bool = False
    reason: str = ""


class ActionResult(BaseModel):
    action_id: str
    status: str
    reason: str = ""


class ValidationResult(BaseModel):
    valid: bool = True
    errors: list[str] = Field(default_factory=list)
    filtered_actions: list[Action] = Field(default_factory=list)
