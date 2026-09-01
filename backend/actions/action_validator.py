from __future__ import annotations

import logging
import re
from typing import Any

from backend.config.settings import SUPPORTED_ACTION_TYPES, VALID_PLACEHOLDERS
from backend.schemas.browser_state import BrowserState

logger = logging.getLogger("browserauto.actions")


def _fuzzy_match_target(target: str, elements: list) -> str | None:
    target_lower = target.lower().replace("_", "").replace("-", "").replace(" ", "")
    if not target_lower:
        return None
    best_match = None
    best_score = 0
    for e in elements:
        eid = e.element_id.lower().replace("_", "").replace("-", "").replace(" ", "")
        label = (e.label or "").lower().replace("_", "").replace("-", "").replace(" ", "")
        text = (e.text or "").lower().replace("_", "").replace("-", "").replace(" ", "")
        if not eid and not label and not text:
            continue
        if target_lower == eid:
            return e.element_id
        if label and target_lower == label:
            return e.element_id
        if text and target_lower == text:
            return e.element_id
        score = 0
        if label and (target_lower in label or label in target_lower):
            score = len(set(target_lower) & set(label))
        elif text and (target_lower in text or text in target_lower):
            score = len(set(target_lower) & set(text))
        elif target_lower in eid or eid in target_lower:
            score = len(set(target_lower) & set(eid)) * 0.5
        if score > best_score:
            best_score = score
            best_match = e.element_id
            logger.debug("Fuzzy candidate: '%s' vs '%s' (eid=%s) score=%.1f", target, e.label or e.text, e.element_id, score)
    if best_match and best_score >= 1:
        logger.info("Fuzzy matched target '%s' -> '%s' (score=%.1f)", target, best_match, best_score)
    return best_match if best_score >= 1 else None


class ActionValidator:
    def validate(
        self,
        actions: list[dict[str, Any]],
        browser_state: BrowserState,
        available_keys: dict[str, str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        valid_actions: list[dict[str, Any]] = []
        errors: list[str] = []

        element_ids = {e.element_id for e in browser_state.elements}
        visible_ids = {e.element_id for e in browser_state.elements if e.enabled}
        available_key_names = set(available_keys.keys()) if available_keys else set()

        for action in actions:
            target = action.get("target", "")
            if target and target not in element_ids:
                matched = _fuzzy_match_target(target, browser_state.elements)
                if matched:
                    action["target"] = matched
                    logger.info("Fuzzy matched target '%s' -> '%s'", target, matched)

            action_errors = self._validate_single(action, element_ids, visible_ids, available_key_names)
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
        available_key_names: set[str] | None = None,
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
            key = action.get("key", "")

            if key:
                if available_key_names and key not in available_key_names:
                    errors.append(f"[{action_id}] Key '{key}' not in available_keys")
            elif value:
                for forbidden in ("javascript:", "eval(", "exec(", "import os", "subprocess"):
                    if forbidden in value.lower():
                        errors.append(f"[{action_id}] Suspicious content in fill value: '{forbidden}'")
                        break
                if value not in VALID_PLACEHOLDERS:
                    errors.append(
                        f"[{action_id}] Fill value '{value}' is not a valid semantic placeholder. "
                        f"Allowed: {', '.join(sorted(VALID_PLACEHOLDERS))}"
                    )
            else:
                errors.append(f"[{action_id}] Fill action requires either 'key' or 'value'")

        if action_type == "scroll":
            direction = action.get("direction", "").lower()
            if direction and direction not in ("up", "down", "left", "right"):
                errors.append(f"[{action_id}] Invalid scroll direction: '{direction}'")

        if action_type == "press_key":
            if not action.get("key"):
                errors.append(f"[{action_id}] press_key requires a 'key' field")

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
