from __future__ import annotations

import logging
from typing import Any

from backend.schemas.browser_state import BrowserState, ElementState

logger = logging.getLogger("browserauto.validation")


class BrowserStateValidator:
    def validate_transition(
        self,
        previous_state: BrowserState | None,
        current_state: BrowserState,
        previous_actions: list[dict[str, Any]],
        execution_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        if not previous_actions:
            return results

        elements_before = {e.element_id: e for e in (previous_state.elements if previous_state else [])}
        elements_after = {e.element_id: e for e in current_state.elements}

        for action in previous_actions:
            action_id = action.get("action_id", "unknown")
            action_type = action.get("type", "")
            target = action.get("target", "")

            result = self._validate_single_action(
                action_type, action, target, elements_before, elements_after,
                previous_state, current_state,
            )
            results.append(result)

        return results

    def _validate_single_action(
        self,
        action_type: str,
        action: dict[str, Any],
        target: str,
        elements_before: dict[str, ElementState],
        elements_after: dict[str, ElementState],
        previous_state: BrowserState | None,
        current_state: BrowserState,
    ) -> dict[str, Any]:
        action_id = action.get("action_id", "unknown")

        if action_type == "fill":
            return self._validate_fill(action_id, target, action, elements_before, elements_after)
        elif action_type == "click":
            return self._validate_click(action_id, target, previous_state, current_state)
        elif action_type == "check":
            return self._validate_check(action_id, target, elements_before, elements_after, True)
        elif action_type == "uncheck":
            return self._validate_check(action_id, target, elements_before, elements_after, False)
        elif action_type == "scroll":
            return self._validate_scroll(action_id, previous_state, current_state)
        elif action_type == "select":
            return self._validate_select(action_id, target, action, elements_before, elements_after)
        elif action_type == "done":
            return {"action_id": action_id, "status": "success", "reason": "Task completed"}
        elif action_type == "wait":
            return {"action_id": action_id, "status": "success", "reason": "Wait requested"}
        else:
            return {"action_id": action_id, "status": "success", "reason": f"Action type '{action_type}' accepted"}

    def _validate_fill(
        self,
        action_id: str,
        target: str,
        action: dict[str, Any],
        elements_before: dict[str, ElementState],
        elements_after: dict[str, ElementState],
    ) -> dict[str, Any]:
        before = elements_before.get(target)
        after = elements_after.get(target)

        if after is None and before is not None:
            return {"action_id": action_id, "status": "success", "reason": "Field filled (element state not re-reported)"}

        if before is None and after is None:
            return {"action_id": action_id, "status": "unknown", "reason": f"Element {target} not found in either state"}

        if before and after:
            if before.value != after.value:
                return {"action_id": action_id, "status": "success", "reason": f"Value changed from '{before.value}' to '{after.value}'"}

        return {"action_id": action_id, "status": "failed", "reason": "No observable state change"}

    def _validate_click(
        self,
        action_id: str,
        target: str,
        previous_state: BrowserState | None,
        current_state: BrowserState,
    ) -> dict[str, Any]:
        if previous_state and current_state.page.url != previous_state.page.url:
            return {"action_id": action_id, "status": "success", "reason": "Page navigated"}

        if previous_state and current_state.page.title != previous_state.page.title:
            return {"action_id": action_id, "status": "success", "reason": "Page title changed"}

        if previous_state and current_state.page.scroll.y != previous_state.page.scroll.y:
            return {"action_id": action_id, "status": "success", "reason": "Page scrolled after click"}

        prev_elements = {e.element_id: e for e in previous_state.elements} if previous_state else {}
        curr_elements = {e.element_id: e for e in current_state.elements}

        prev_focused = {eid for eid, e in prev_elements.items() if e.focused}
        curr_focused = {eid for eid, e in curr_elements.items() if e.focused}

        if target in curr_focused and target not in prev_focused:
            return {"action_id": action_id, "status": "success", "reason": "Element focused after click"}

        return {"action_id": action_id, "status": "failed", "reason": "No observable state change after click"}

    def _validate_check(
        self,
        action_id: str,
        target: str,
        elements_before: dict[str, ElementState],
        elements_after: dict[str, ElementState],
        expected_checked: bool,
    ) -> dict[str, Any]:
        before = elements_before.get(target)
        after = elements_after.get(target)

        if after is None and before is not None:
            return {"action_id": action_id, "status": "success", "reason": "Checkbox toggled"}

        if before and after and before.checked != after.checked:
            if after.checked == expected_checked:
                return {"action_id": action_id, "status": "success", "reason": f"Checkbox now {'checked' if expected_checked else 'unchecked'}"}

        return {"action_id": action_id, "status": "failed", "reason": "No observable state change"}

    def _validate_scroll(
        self,
        action_id: str,
        previous_state: BrowserState | None,
        current_state: BrowserState,
    ) -> dict[str, Any]:
        if previous_state:
            if current_state.page.scroll.y != previous_state.page.scroll.y:
                return {"action_id": action_id, "status": "success", "reason": "Scroll position changed"}
        return {"action_id": action_id, "status": "failed", "reason": "No observable scroll change"}

    def _validate_select(
        self,
        action_id: str,
        target: str,
        action: dict[str, Any],
        elements_before: dict[str, ElementState],
        elements_after: dict[str, ElementState],
    ) -> dict[str, Any]:
        before = elements_before.get(target)
        after = elements_after.get(target)

        if after is None and before is not None:
            return {"action_id": action_id, "status": "success", "reason": "Select changed"}

        if before and after and before.value != after.value:
            return {"action_id": action_id, "status": "success", "reason": f"Select value changed"}

        return {"action_id": action_id, "status": "failed", "reason": "No observable select change"}
