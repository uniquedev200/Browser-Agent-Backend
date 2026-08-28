from __future__ import annotations

import pytest

from backend.schemas.browser_state import BrowserState, ElementState, PageMetadata, ScrollPosition, Viewport
from backend.validation.browser_state_validator import BrowserStateValidator


@pytest.fixture
def validator():
    return BrowserStateValidator()


def _state(elements, url="https://example.com", title="Page", scroll_y=0):
    return BrowserState(
        page=PageMetadata(
            title=title,
            url=url,
            viewport=Viewport(width=1440, height=900),
            scroll=ScrollPosition(x=0, y=scroll_y),
        ),
        elements=[ElementState(**e) for e in elements],
    )


def test_validate_fill_success(validator):
    before = _state([
        {"element_id": "el_1", "role": "textbox", "value": "", "label": "Name"},
    ])
    after = _state([
        {"element_id": "el_1", "role": "textbox", "value": "<PERSON>", "label": "Name"},
    ])
    results = validator.validate_transition(before, after, [{"action_id": "a1", "type": "fill", "target": "el_1"}], [])
    assert results[0]["status"] == "success"


def test_validate_fill_no_change(validator):
    before = _state([
        {"element_id": "el_1", "role": "textbox", "value": "", "label": "Name"},
    ])
    after = _state([
        {"element_id": "el_1", "role": "textbox", "value": "", "label": "Name"},
    ])
    results = validator.validate_transition(before, after, [{"action_id": "a1", "type": "fill", "target": "el_1"}], [])
    assert results[0]["status"] == "failed"


def test_validate_click_navigation(validator):
    before = _state([], url="https://example.com/page1", title="Page 1")
    after = _state([], url="https://example.com/page2", title="Page 2")
    results = validator.validate_transition(before, after, [{"action_id": "a1", "type": "click", "target": "btn"}], [])
    assert results[0]["status"] == "success"
    assert "navigated" in results[0]["reason"].lower()


def test_validate_check_success(validator):
    before = _state([
        {"element_id": "cb_1", "role": "checkbox", "checked": False},
    ])
    after = _state([
        {"element_id": "cb_1", "role": "checkbox", "checked": True},
    ])
    results = validator.validate_transition(before, after, [{"action_id": "a1", "type": "check", "target": "cb_1"}], [])
    assert results[0]["status"] == "success"


def test_validate_scroll_success(validator):
    before = _state([], scroll_y=0)
    after = _state([], scroll_y=780)
    results = validator.validate_transition(before, after, [{"action_id": "a1", "type": "scroll"}], [])
    assert results[0]["status"] == "success"


def test_validate_scroll_no_change(validator):
    before = _state([], scroll_y=0)
    after = _state([], scroll_y=0)
    results = validator.validate_transition(before, after, [{"action_id": "a1", "type": "scroll"}], [])
    assert results[0]["status"] == "failed"


def test_validate_done(validator):
    state = _state([])
    results = validator.validate_transition(state, state, [{"action_id": "a1", "type": "done"}], [])
    assert results[0]["status"] == "success"


def test_validate_wait(validator):
    state = _state([])
    results = validator.validate_transition(state, state, [{"action_id": "a1", "type": "wait"}], [])
    assert results[0]["status"] == "success"


def test_validate_select_success(validator):
    before = _state([
        {"element_id": "sel_1", "role": "combobox", "value": ""},
    ])
    after = _state([
        {"element_id": "sel_1", "role": "combobox", "value": "option_a"},
    ])
    results = validator.validate_transition(before, after, [{"action_id": "a1", "type": "select", "target": "sel_1"}], [])
    assert results[0]["status"] == "success"


def test_no_actions_returns_empty(validator):
    state = _state([])
    results = validator.validate_transition(state, state, [], [])
    assert results == []
