from __future__ import annotations

import pytest

from backend.schemas.session import SessionData
from backend.workflow.workflow_manager import WorkflowManager


@pytest.fixture
def wm():
    return WorkflowManager()


@pytest.fixture
def running_session():
    return SessionData(
        session_id="sess_wf_test",
        task="Complete form",
        status="RUNNING",
        phase="",
        summary="",
        step_index=0,
        retry_count=0,
    )


def test_update_after_execution(wm, running_session):
    wm.update_after_execution(
        session=running_session,
        previous_browser_state_hash="",
        current_browser_state_hash="abc123",
        action_batch=[{"action_id": "a1", "type": "fill", "target": "el_1"}],
        execution_results=[],
        validation_results=[{"action_id": "a1", "status": "success"}],
    )
    assert running_session.step_index == 1
    assert running_session.retry_count == 0
    assert running_session.last_browser_state_hash == "abc123"


def test_update_summary(wm, running_session):
    wm.update_summary(running_session, "personal_info", "Filled name field", [])
    assert running_session.phase == "personal_info"
    assert "Filled name field" in running_session.summary


def test_should_continue_running(wm, running_session):
    assert wm.should_continue(running_session) is True


def test_should_continue_blocked(wm, running_session):
    running_session.status = "BLOCKED"
    assert wm.should_continue(running_session) is False


def test_should_continue_completed(wm, running_session):
    running_session.status = "COMPLETED"
    assert wm.should_continue(running_session) is False


def test_mark_completed(wm, running_session):
    wm.mark_completed(running_session)
    assert running_session.status == "COMPLETED"


def test_mark_blocked(wm, running_session):
    wm.mark_blocked(running_session, "Too many retries")
    assert running_session.status == "BLOCKED"
    assert "Too many retries" in running_session.summary


def test_retry_increment(wm, running_session):
    wm.update_after_execution(
        session=running_session,
        previous_browser_state_hash="",
        current_browser_state_hash="hash1",
        action_batch=[{"action_id": "a1"}],
        execution_results=[],
        validation_results=[{"action_id": "a1", "status": "failed"}],
    )
    assert running_session.retry_count == 1


def test_retry_reset_on_success(wm, running_session):
    running_session.retry_count = 2
    wm.update_after_execution(
        session=running_session,
        previous_browser_state_hash="hash1",
        current_browser_state_hash="hash2",
        action_batch=[{"action_id": "a1"}],
        execution_results=[],
        validation_results=[{"action_id": "a1", "status": "success"}],
    )
    assert running_session.retry_count == 0


def test_detect_loop(wm, running_session):
    running_session.last_browser_state_hash = "same_hash"
    running_session.previous_browser_state_hash = "same_hash"
    running_session.retry_count = 3
    assert wm.detect_loop(running_session) is True


def test_no_loop_different_hashes(wm, running_session):
    running_session.last_browser_state_hash = "hash_a"
    running_session.previous_browser_state_hash = "hash_b"
    running_session.retry_count = 3
    assert wm.detect_loop(running_session) is False


def test_is_page_terminating_click(wm):
    from backend.schemas.action import Action

    action = Action(action_id="a1", type="click", target="el_1", value="Submit")
    assert wm.is_page_terminating(action) is True


def test_is_page_terminating_fill(wm):
    from backend.schemas.action import Action

    action = Action(action_id="a1", type="fill", target="el_1", value="<EMAIL>")
    assert wm.is_page_terminating(action) is False


def test_is_page_terminating_scroll(wm):
    from backend.schemas.action import Action

    action = Action(action_id="a1", type="scroll", target="el_1")
    assert wm.is_page_terminating(action) is True


def test_workflow_multistep_lifecycle(wm):
    session = SessionData(session_id="sess_multistep", task="Apply", status="RUNNING")

    phases = ["personal_info", "education", "review", "completed"]
    for i, phase in enumerate(phases[:-1]):
        wm.update_summary(session, phase, f"Working on {phase}", [])
        assert session.phase == phase
        assert session.step_index <= i + 1

    wm.mark_completed(session)
    assert session.status == "COMPLETED"
