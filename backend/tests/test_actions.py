from __future__ import annotations

import pytest

from backend.actions.action_validator import ActionValidator
from backend.schemas.browser_state import BrowserState, ElementState, PageMetadata, ScrollPosition, Viewport


@pytest.fixture
def validator():
    return ActionValidator()


def _state(elements):
    return BrowserState(
        page=PageMetadata(title="Test", url="https://example.com"),
        elements=[ElementState(**e) for e in elements],
    )


def test_valid_fill_action(validator):
    state = _state([
        {"element_id": "el_1", "role": "textbox", "label": "Name", "enabled": True},
    ])
    actions = [{"action_id": "a1", "type": "fill", "target": "el_1", "value": "<PERSON>"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 1
    assert len(errors) == 0


def test_valid_click_action(validator):
    state = _state([
        {"element_id": "btn_1", "role": "button", "text": "Submit", "enabled": True},
    ])
    actions = [{"action_id": "a1", "type": "click", "target": "btn_1"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 1


def test_unknown_action_type(validator):
    state = _state([
        {"element_id": "el_1", "role": "textbox", "enabled": True},
    ])
    actions = [{"action_id": "a1", "type": "hack_system", "target": "el_1"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 0
    assert len(errors) > 0


def test_nonexistent_element(validator):
    state = _state([
        {"element_id": "el_1", "role": "textbox", "enabled": True},
    ])
    actions = [{"action_id": "a1", "type": "click", "target": "el_999"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 0
    assert len(errors) > 0
    assert "does not exist" in errors[0]


def test_disabled_element(validator):
    state = _state([
        {"element_id": "el_1", "role": "textbox", "enabled": False},
    ])
    actions = [{"action_id": "a1", "type": "fill", "target": "el_1", "value": "<EMAIL>"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 0
    assert len(errors) > 0


def test_done_action_no_target(validator):
    state = _state([])
    actions = [{"action_id": "a1", "type": "done"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 1


def test_wait_action_no_target(validator):
    state = _state([])
    actions = [{"action_id": "a1", "type": "wait"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 1


def test_press_key_requires_key(validator):
    state = _state([])
    actions = [{"action_id": "a1", "type": "press_key"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 0
    assert len(errors) > 0


def test_press_key_with_key(validator):
    state = _state([])
    actions = [{"action_id": "a1", "type": "press_key", "key": "Enter"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 1


def test_scroll_invalid_direction(validator):
    state = _state([])
    actions = [{"action_id": "a1", "type": "scroll", "direction": "diagonal"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 0


def test_scroll_valid_direction(validator):
    state = _state([])
    actions = [{"action_id": "a1", "type": "scroll", "direction": "down"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 1


def test_javascript_injection_rejected(validator):
    state = _state([
        {"element_id": "el_1", "role": "textbox", "enabled": True},
    ])
    actions = [{"action_id": "a1", "type": "fill", "target": "el_1", "value": "javascript:alert(1)"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 0
    assert len(errors) > 0


def test_batch_valid_actions(validator):
    state = _state([
        {"element_id": "el_1", "role": "textbox", "label": "Name", "enabled": True},
        {"element_id": "el_2", "role": "textbox", "label": "Email", "enabled": True},
        {"element_id": "el_3", "role": "button", "text": "Submit", "enabled": True},
    ])
    actions = [
        {"action_id": "a1", "type": "fill", "target": "el_1", "value": "<PERSON>"},
        {"action_id": "a2", "type": "fill", "target": "el_2", "value": "<EMAIL>"},
    ]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 2
    assert len(errors) == 0


def test_unknown_placeholder_rejected(validator):
    state = _state([
        {"element_id": "el_1", "role": "textbox", "label": "Alt Email", "enabled": True},
    ])
    actions = [{"action_id": "a1", "type": "fill", "target": "el_1", "value": "<ALT_EMAIL>"}]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 0
    assert len(errors) == 1
    assert "not a valid semantic placeholder" in errors[0]


def test_invalid_model_action_rejection(validator):
    state = _state([
        {"element_id": "el_1", "role": "textbox", "enabled": True},
    ])
    actions = [
        {"action_id": "a1", "type": "execute_code", "target": "el_1"},
        {"action_id": "a2", "type": "shell_command", "target": "el_1"},
        {"action_id": "a3", "type": "delete_file", "target": "el_1"},
    ]
    valid, errors = validator.validate(actions, state)
    assert len(valid) == 0
    assert len(errors) == 3
