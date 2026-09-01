from __future__ import annotations

import logging
from typing import Any

from backend.config.settings import MAX_RETRIES
from backend.schemas.action import Action, ActionBatch, ActionResult
from backend.schemas.browser_state import BrowserState
from backend.schemas.session import SessionData

logger = logging.getLogger("browserauto.workflow")

PAGE_TERMINATORS = {"click", "upload", "scroll"}

SUCCESS_INDICATORS = {
    "submitted", "success", "thank you", "thank you!",
    "confirmation", "confirmed", "complete", "completed",
    "received", "saved", "done", "congratulations",
    "application submitted", "form submitted", "registration complete",
}


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

        session.touch_updated()

    def check_completion(
        self,
        session: SessionData,
        current_state: BrowserState,
        previous_state: BrowserState | None,
        action_batch: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        page_text = (current_state.page.title + " " + current_state.page.url).lower()
        for indicator in SUCCESS_INDICATORS:
            if indicator in page_text:
                logger.info("Session %s: success indicator detected '%s'", session.session_id, indicator)
                return True, f"Success message detected: {indicator}"

        if previous_state:
            prev_url = previous_state.page.url.lower()
            curr_url = current_state.page.url.lower()
            prev_title = previous_state.page.title.lower()
            curr_title = current_state.page.title.lower()

            if prev_url and curr_url and prev_url != curr_url:
                logger.info("Session %s: page navigation detected %s -> %s", session.session_id, prev_url, curr_url)
                return True, f"Page navigated: {prev_url} -> {curr_url}"

            if prev_title and curr_title and prev_title != curr_title:
                logger.info("Session %s: title changed '%s' -> '%s'", session.session_id, prev_title, curr_title)
                return True, f"Page title changed: {prev_title} -> {curr_title}"

        if action_batch:
            click_actions = [a for a in action_batch if a.get("type") == "click"]
            submit_keywords = {"submit", "next", "continue", "register", "sign up", "login", "save", "send", "confirm"}
            for ca in click_actions:
                target = (ca.get("target", "") or "").lower()
                if any(kw in target for kw in submit_keywords):
                    logger.info("Session %s: submit button clicked '%s'", session.session_id, target)

        all_interactive = [
            e for e in current_state.elements
            if e.role in ("textbox", "checkbox", "combobox")
        ]
        if all_interactive:
            filled_count = 0
            for e in all_interactive:
                if e.role == "checkbox":
                    if e.checked:
                        filled_count += 1
                elif e.role == "textbox":
                    if e.value and e.value != "empty" and not e.value.startswith("<"):
                        filled_count += 1
                elif e.role == "combobox":
                    if e.selected:
                        filled_count += 1

            if filled_count == len(all_interactive):
                logger.info("Session %s: all %d interactive elements filled", session.session_id, len(all_interactive))
                return True, f"All {len(all_interactive)} form fields completed"

        return False, ""

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
