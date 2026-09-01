from __future__ import annotations

import json
import logging
from typing import Any

from backend.schemas.browser_state import BrowserState

logger = logging.getLogger("browserauto.prompts")


class PromptBuilder:
    def __init__(self, version: str = "1.0") -> None:
        self.version = version

    def build(
        self,
        task: str,
        session_summary: str,
        phase: str,
        browser_state: BrowserState,
        previous_actions: list[dict[str, Any]] | None = None,
        validation_results: list[dict[str, Any]] | None = None,
        execution_results: list[dict[str, Any]] | None = None,
        available_keys: dict[str, str] | None = None,
    ) -> str:
        visible_elements, offscreen_elements = self._split_by_visibility(browser_state)
        pending_visible, completed_visible = self._categorize_elements(visible_elements)
        pending_offscreen, _ = self._categorize_elements(offscreen_elements)

        needs_scroll = len(pending_offscreen) > 0 and len(pending_visible) == 0
        all_done = len(pending_visible) == 0 and len(pending_offscreen) == 0

        if all_done:
            return self._build_done_response(task, completed_visible)

        key_names = list(available_keys.keys()) if available_keys else []
        has_keys = len(key_names) > 0

        example_actions = self._build_example(pending_visible, has_keys, key_names)

        parts: list[str] = []
        parts.append(
            "You are a browser automation agent. Return ONLY compact JSON.\n\n"
            "ACTION TYPES:\n"
            "- \"fill\" for empty textboxes (use \"key\" field to reference user data)\n"
            "- \"check\" for unchecked checkboxes (no value needed)\n"
            "- \"click\" for buttons (no value needed)\n"
            "- \"scroll\" to reveal off-screen elements (use \"direction\":\"down\")\n\n"
            "RULES:\n"
            "- The \"target\" field MUST be the element_id from the list below\n"
            "- For fill actions, use the \"key\" field with the matching key from Available Keys\n"
            "- If there are off-screen elements that need action, include a scroll action FIRST\n"
            "- Only return {\"status\":\"done\"} when ALL elements are filled/checked\n"
            "- Return ALL actions in a SINGLE array\n"
        )

        if task:
            parts.append(f"Task: {task}")

        if phase:
            parts.append(f"Phase: {phase}")

        if previous_actions:
            parts.append(f"Prev: {json.dumps(previous_actions)}")

        if key_names:
            parts.append(f"\nAvailable Keys: {', '.join(key_names)}")

        if pending_visible:
            parts.append("\nVisible elements (need action):")
            parts.extend(pending_visible)

        if pending_offscreen:
            parts.append("\nOff-screen elements (need scroll + action):")
            parts.extend(pending_offscreen)

        if completed_visible:
            parts.append("\nCompleted elements:")
            parts.extend(completed_visible)

        if example_actions:
            parts.append(f"\nExample output:")
            parts.append(example_actions)

        parts.append("")

        return "\n".join(parts)

    def _split_by_visibility(
        self, browser_state: BrowserState
    ) -> tuple[list, list]:
        viewport = browser_state.page.viewport
        scroll = browser_state.page.scroll
        visible = []
        offscreen = []

        for e in browser_state.elements:
            if e.role not in ("textbox", "button", "checkbox", "combobox"):
                continue

            if not e.bbox or len(e.bbox) < 4:
                visible.append(e)
                continue

            el_y = e.bbox[1] - scroll.y
            el_bottom = el_y + e.bbox[3]
            vp_top = 0
            vp_bottom = viewport.height

            if el_bottom > vp_top and el_y < vp_bottom:
                visible.append(e)
            else:
                offscreen.append(e)

        return visible, offscreen

    def _categorize_elements(
        self, elements: list
    ) -> tuple[list[str], list[str]]:
        pending = []
        completed = []

        for e in elements:
            label = e.label or e.text or e.element_id
            needs_action = False

            if e.role == "textbox":
                if not e.value or e.value.startswith("<") or e.value == "empty":
                    needs_action = True
                state = e.value if e.value and e.value != "empty" else "empty"
            elif e.role == "checkbox":
                if not e.checked:
                    needs_action = True
                state = "checked" if e.checked else "unchecked"
            elif e.role in ("button", "combobox"):
                needs_action = True
                state = e.value if e.value else "empty"

            line = f"- {e.element_id}: {e.role} \"{label}\" ({state})"
            if needs_action:
                pending.append(line)
            else:
                completed.append(line)

        return pending, completed

    def _build_done_response(self, task: str, completed: list[str]) -> str:
        parts: list[str] = []
        parts.append(
            "You are a browser automation agent. Return ONLY compact JSON.\n\n"
            "All form elements are already filled and checked.\n"
            "Return: {\"status\":\"done\",\"phase\":\"done\",\"actions\":[],\"checkpoint\":true,\"reason\":\"All fields filled\"}\n"
        )
        if task:
            parts.append(f"Task: {task}")

        if completed:
            parts.append("\nAll elements are completed:")
            parts.extend(completed)

        parts.append("")
        return "\n".join(parts)

    def _build_example(
        self, elements: list[str], has_keys: bool, key_names: list[str]
    ) -> str:
        textboxes = []
        checkbox = None
        buttons = []

        for line in elements:
            if "textbox" in line:
                eid = line.split(":")[0].strip("- ")
                textboxes.append(eid)
            elif "checkbox" in line and checkbox is None:
                eid = line.split(":")[0].strip("- ")
                checkbox = eid
            elif "button" in line:
                eid = line.split(":")[0].strip("- ")
                buttons.append(eid)

        actions = []
        i = 1
        if has_keys:
            key_map = {}
            keywords = {
                "name": ["name", "full name", "first name", "last name"],
                "email": ["email", "e-mail"],
                "phone": ["phone", "mobile", "tel"],
                "address": ["address", "street", "city"],
            }
            for kn in key_names:
                kn_lower = kn.lower()
                for field_type, words in keywords.items():
                    if any(w in kn_lower for w in words):
                        key_map[field_type] = kn
                        break

            for eid in textboxes[:4]:
                eid_lower = eid.lower()
                matched_key = None
                for field_type, kn in key_map.items():
                    if field_type in eid_lower:
                        matched_key = kn
                        break
                if not matched_key and i - 1 < len(key_names):
                    matched_key = key_names[i - 1]

                action = {"action_id": f"a{i}", "type": "fill", "target": eid}
                if matched_key:
                    action["key"] = matched_key
                actions.append(action)
                i += 1
        else:
            placeholders = ["<PERSON>", "<EMAIL>", "<PHONE>", "<ADDRESS>"]
            for j, eid in enumerate(textboxes[:4]):
                ph = placeholders[j] if j < len(placeholders) else "<PERSON>"
                actions.append({"action_id": f"a{i}", "type": "fill", "target": eid, "value": ph})
                i += 1

        if checkbox:
            actions.append({"action_id": f"a{i}", "type": "check", "target": checkbox})
            i += 1

        for btn in buttons:
            actions.append({"action_id": f"a{i}", "type": "click", "target": btn})
            i += 1

        return json.dumps(
            {"status": "continue", "phase": "fill", "actions": actions, "checkpoint": True, "reason": "filling form"},
            separators=(",", ":"),
        )
