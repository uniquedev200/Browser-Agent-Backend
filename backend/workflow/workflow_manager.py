from __future__ import annotations

import logging
from typing import Any

from backend.config.settings import MAX_RETRIES
from backend.schemas.action import Action, ActionBatch, ActionResult
from backend.schemas.session import SessionData

logger = logging.getLogger("browserauto.workflow")

PAGE_TERMINATORS = {"click", "upload", "scroll"}


class WorkflowManager:
    def update_after_execution(
        self,
        session: SessionData,
        previous_browser_state_hash: str,
        current_browser_state_hash: str,
        action_batch: list[dict[str, Any]],
        execution_results: list[dict[str, Any]],
        validation_results: list[dict[str, Any]],
    ) -> None:
        session.previous_browser_state_hash = previous_browser_state_hash
        session.last_browser_state_hash = current_browser_state_hash

        if action_batch:
            session.last_action_batch = action_batch
            session.step_index += 1

        failed_count = 0
        for vr in validation_results:
            if vr.get("status") == "failed":
                failed_count += 1

        if failed_count > 0:
            session.retry_count += 1
            logger.debug(
                "Session %s: %d validation failures, retry_count=%d",
                session.session_id,
                failed_count,
                session.retry_count,
            )
        else:
            session.retry_count = 0

        if session.retry_count >= MAX_RETRIES:
            session.status = "BLOCKED"
            logger.warning(
                "Session %s: blocked after %d retries",
                session.session_id,
                session.retry_count,
            )

        url = ""
        if hasattr(session, "_last_page_url"):
            url = session._last_page_url

        session.touch_updated()

    def update_summary(
        self,
        session: SessionData,
        phase: str,
        reason: str,
        action_batch: list[dict[str, Any]],
    ) -> None:
        if phase:
            session.phase = phase

        if reason:
            if session.summary:
                session.summary = f"{session.summary} {reason}"
            else:
                session.summary = reason

        if len(session.summary) > 500:
            session.summary = session.summary[-500:]

    def should_continue(self, session: SessionData) -> bool:
        if session.status != "RUNNING":
            return False
        if session.retry_count >= MAX_RETRIES:
            return False
        return True

    def mark_completed(self, session: SessionData) -> None:
        session.status = "COMPLETED"
        session.touch_updated()

    def mark_blocked(self, session: SessionData, reason: str = "") -> None:
        session.status = "BLOCKED"
        if reason:
            session.summary = f"{session.summary} BLOCKED: {reason}"
        session.touch_updated()

    def detect_loop(self, session: SessionData) -> bool:
        if (
            session.last_browser_state_hash
            and session.last_browser_state_hash == session.previous_browser_state_hash
            and session.retry_count >= 2
        ):
            logger.warning(
                "Session %s: loop detected (same state hash repeated)", session.session_id
            )
            return True
        return False

    def is_page_terminating(self, action: Action) -> bool:
        if action.type in PAGE_TERMINATORS:
            return True
        if action.type == "click":
            text = (action.value or "").lower()
            terminators = {"submit", "next", "login", "sign in", "continue", "register", "save"}
            if any(t in text for t in terminators):
                return True
        return False
