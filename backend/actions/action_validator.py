from __future__ import annotations

import logging
import re
from typing import Any

from backend.config.settings import SUPPORTED_ACTION_TYPES, VALID_PLACEHOLDERS
from backend.schemas.browser_state import BrowserState

logger = logging.getLogger("browserauto.actions")


class ActionValidator:
    def validate(
        self,
        actions: list[dict[str, Any]],
        browser_state: BrowserState,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        valid_actions: list[dict[str, Any]] = []
        errors: list[str] = []

        element_ids = {e.element_id for e in browser_state.elements}
        visible_ids = {e.element_id for e in browser_state.elements if e.enabled}

        for action in actions:
            action_errors = self._validate_single(action, element_ids, visible_ids)
            if action_errors:
                errors.extend(action_errors)
            else:
                valid_actions.append(action)

        return valid_actions, errors

    def _validate_single(
        self,
        action: dict[str, Any],
        element_ids: set[str],
        visible_ids: set[str],
    ) -> list[str]:
        errors: list[str] = []
        action_id = action.get("action_id", "unknown")
        action_type = action.get("type", "")
        target = action.get("target", "")

        if action_type not in SUPPORTED_ACTION_TYPES:
            errors.append(f"[{action_id}] Unknown action type: '{action_type}'")
            return errors

        if action_type == "done":
            return []

        if action_type == "wait":
            return []

        if action_type in ("click", "fill", "select", "check", "uncheck"):
            if not target:
                errors.append(f"[{action_id}] Action '{action_type}' requires a target")
            elif target not in element_ids:
                errors.append(f"[{action_id}] Target element '{target}' does not exist")
            elif target not in visible_ids:
                errors.append(f"[{action_id}] Target element '{target}' is not interactable")

        if action_type == "fill":
            value = action.get("value", "")
            if value:
                for forbidden in ("javascript:", "eval(", "exec(", "import os", "subprocess"):
                    if forbidden in value.lower():
                        errors.append(f"[{action_id}] Suspicious content in fill value: '{forbidden}'")
                        break

                if value not in VALID_PLACEHOLDERS:
                    errors.append(
                        f"[{action_id}] Fill value '{value}' is not a valid semantic placeholder. "
                        f"Allowed: {', '.join(sorted(VALID_PLACEHOLDERS))}"
                    )

        if action_type == "press_key":
            if not action.get("key"):
                errors.append(f"[{action_id}] press_key requires a 'key' field")

        if action_type == "scroll":
            direction = action.get("direction", "").lower()
            if direction and direction not in ("up", "down", "left", "right"):
                errors.append(f"[{action_id}] Invalid scroll direction: '{direction}'")

        forbidden_patterns = [
            r"javascript\s*:",
            r"<script",
            r"eval\s*\(",
            r"exec\s*\(",
            r"import\s+os",
            r"subprocess",
            r"__import__",
            r"system\s*\(",
        ]
        action_str = str(action).lower()
        for pattern in forbidden_patterns:
            if re.search(pattern, action_str):
                errors.append(f"[{action_id}] Potentially malicious content detected")
                break

        return errors
