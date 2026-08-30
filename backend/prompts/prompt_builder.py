from __future__ import annotations

import json
from typing import Any

from backend.config.settings import VALID_PLACEHOLDERS
from backend.schemas.browser_state import BrowserState


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
    ) -> str:
        pending_elements = []
        completed_elements = []

        for e in browser_state.elements:
            if e.role not in ("textbox", "button", "checkbox", "combobox"):
                continue

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
                pending_elements.append(line)
            else:
                completed_elements.append(line)

        all_done = len(pending_elements) == 0

        if all_done:
            return self._build_done_response(task, completed_elements)

        example_actions = self._build_example(pending_elements)

        parts: list[str] = []
        parts.append(
            "You are a form-filling agent. Return ONLY compact JSON.\n\n"
            "ACTION TYPES:\n"
            "- \"fill\" for empty textboxes (use <PERSON>, <EMAIL>, <PHONE>, <ADDRESS> as value)\n"
            "- \"check\" for unchecked checkboxes (no value needed)\n"
            "- \"click\" for buttons (no value needed)\n\n"
            "RULES:\n"
            "- The \"target\" field MUST be the element_id from the list below\n"
            "- The \"value\" field MUST be a placeholder like <EMAIL>, not real data\n"
            "- If \"Pending elements\" is NOT empty, you MUST generate actions for ALL pending elements\n"
            "- Only return {\"status\":\"done\"} when \"Pending elements\" is EMPTY\n"
            "- Return ALL actions in a SINGLE array\n"
        )

        if task:
            parts.append(f"Task: {task}")

        if phase:
            parts.append(f"Phase: {phase}")

        if previous_actions:
            parts.append(f"Prev: {json.dumps(previous_actions)}")

        if pending_elements:
            parts.append("\nPending elements (need action):")
            parts.extend(pending_elements)

        if completed_elements:
            parts.append("\nCompleted elements:")
            parts.extend(completed_elements)

        if example_actions:
            parts.append(f"\nExample output:")
            parts.append(example_actions)

        parts.append("")

        return "\n".join(parts)

    def _build_done_response(self, task: str, completed: list[str]) -> str:
        parts: list[str] = []
        parts.append(
            "You are a form-filling agent. Return ONLY compact JSON.\n\n"
            "All form elements are already filled and checked.\n"
            "Return: {\"status\":\"done\",\"phase\":\"done\",\"actions\":[],\"checkpoint\":true,\"reason\":\"All fields filled and submitted\"}\n"
        )
        if task:
            parts.append(f"Task: {task}")

        if completed:
            parts.append("\nAll elements are completed:")
            parts.extend(completed)

        parts.append("")
        return "\n".join(parts)

    def _build_example(self, elements: list[str]) -> str:
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

        return json.dumps({"status": "continue", "phase": "fill", "actions": actions, "checkpoint": True, "reason": "filling form"}, separators=(",", ":"))
