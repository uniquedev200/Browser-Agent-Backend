from __future__ import annotations

import json
from typing import Any

from backend.config.settings import VALID_PLACEHOLDERS
from backend.schemas.browser_state import BrowserState


SYSTEM_PROMPT = """\
You are a form-filling agent. Return JSON with ALL actions for EVERY empty field.

ACTION TYPES (use these exact strings):
- "fill" for textboxes
- "check"/"uncheck" for checkboxes  
- "click" for buttons

OUTPUT FORMAT - return JSON like this:
{"status":"continue","phase":"fill","actions":[{"action_id":"a1","type":"fill","target":"FIELD_ID","value":"<PLACEHOLDER>"},{"action_id":"a2","type":"fill","target":"FIELD_ID","value":"<PLACEHOLDER>"}],"checkpoint":true,"reason":"filling form"}

RULES:
- Create ONE action per empty field
- Use <PERSON>, <EMAIL>, <PHONE>, <ADDRESS> as values
- Use the EXACT element_id from the Elements list as "target"
- Return ALL actions in a SINGLE array\
"""


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
        parts: list[str] = []
        parts.append(SYSTEM_PROMPT)
        parts.append("")

        if task:
            parts.append(f"Task: {task}")

        if phase:
            parts.append(f"Phase: {phase}")

        if previous_actions:
            parts.append(f"Prev: {json.dumps(previous_actions)}")

        elements = []
        for e in browser_state.elements:
            if e.role in ("textbox", "button", "checkbox", "combobox"):
                if e.role == "checkbox":
                    state = "checked" if e.checked else "unchecked"
                    label = e.label or e.text or e.element_id
                    elements.append(f"- {e.element_id}: checkbox \"{label}\" ({state})")
                else:
                    val = e.value if e.value else "empty"
                    label = e.label or e.text or e.element_id
                    elements.append(f"- {e.element_id}: {e.role} \"{label}\" ({val})")

        if elements:
            parts.append("Elements:")
            parts.extend(elements)

        parts.append("")

        return "\n".join(parts)
