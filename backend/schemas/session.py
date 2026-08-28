from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class SessionData(BaseModel):
    session_id: str
    task: str = ""
    status: str = "RUNNING"
    phase: str = ""
    summary: str = ""
    step_index: int = 0
    last_action_batch: list[dict[str, Any]] = Field(default_factory=list)
    last_browser_state_hash: str = ""
    previous_browser_state_hash: str = ""
    retry_count: int = 0
    visited_pages: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def touch_updated(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.updated_at = now

    def ensure_created(self) -> None:
        if not self.created_at:
            now = datetime.now(timezone.utc).isoformat()
            self.created_at = now
            self.updated_at = now
