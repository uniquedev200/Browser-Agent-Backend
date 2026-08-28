from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.actions.action_validator import ActionValidator
from backend.config.settings import DEBUG_TIMINGS
from backend.prompts.prompt_builder import PromptBuilder
from backend.schemas.action import ActionBatch
from backend.schemas.browser_state import BrowserState
from backend.schemas.request import (
    HealthResponse,
    InferRequest,
    InferResponse,
    SessionCreateRequest,
    SessionCreateResponse,
)
from backend.schemas.session import SessionData
from backend.session.session_manager import SessionManager
from backend.utils.hashing import hash_browser_state
from backend.utils.logging import log_request, setup_logging
from backend.validation.browser_state_validator import BrowserStateValidator
from backend.vlm.qwen_engine import QwenVLMEngine
from backend.workflow.workflow_manager import WorkflowManager

logger = logging.getLogger("browserauto.api")

router = APIRouter()

_session_manager: SessionManager | None = None
_workflow_manager: WorkflowManager | None = None
_state_validator: BrowserStateValidator | None = None
_prompt_builder: PromptBuilder | None = None
_vlm_engine: QwenVLMEngine | None = None
_action_validator: ActionValidator | None = None
_timings_enabled: bool = False


def init_routes(
    session_manager: SessionManager,
    workflow_manager: WorkflowManager,
    state_validator: BrowserStateValidator,
    prompt_builder: PromptBuilder,
    vlm_engine: QwenVLMEngine,
    action_validator: ActionValidator,
    debug_timings: bool = False,
) -> None:
    global _session_manager, _workflow_manager, _state_validator
    global _prompt_builder, _vlm_engine, _action_validator, _timings_enabled

    _session_manager = session_manager
    _workflow_manager = workflow_manager
    _state_validator = state_validator
    _prompt_builder = prompt_builder
    _vlm_engine = vlm_engine
    _action_validator = action_validator
    _timings_enabled = debug_timings


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Check if the server is running and healthy."""
    return HealthResponse(status="ok")


@router.post(
    "/api/v1/session",
    response_model=SessionCreateResponse,
    tags=["Sessions"],
    summary="Create or resume a session",
)
async def create_session(req: SessionCreateRequest) -> SessionCreateResponse:
    """Create a new session or resume an existing one by session_id."""
    session = await _session_manager.get_or_create(req.session_id, req.task)
    return SessionCreateResponse(
        session_id=session.session_id,
        status=session.status,
        created_at=session.created_at,
    )


@router.get(
    "/api/v1/session/{session_id}",
    tags=["Sessions"],
    summary="Get session state",
)
async def get_session(session_id: str) -> dict[str, Any]:
    """Retrieve sanitized session state for debugging. Does not expose raw PII."""
    session = await _session_manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "task": session.task,
        "status": session.status,
        "phase": session.phase,
        "summary": session.summary,
        "step_index": session.step_index,
        "retry_count": session.retry_count,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


@router.delete(
    "/api/v1/session/{session_id}",
    tags=["Sessions"],
    summary="Delete a session",
)
async def delete_session(session_id: str) -> dict[str, str]:
    """Delete a session and all associated data (cascade)."""
    deleted = await _session_manager.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


@router.post(
    "/api/v1/infer",
    response_model=InferResponse,
    tags=["Inference"],
    summary="Run VLM inference on browser state",
)
async def infer(req: InferRequest) -> InferResponse:
    timings: dict[str, float] = {}
    total_start = time.perf_counter()

    t0 = time.perf_counter()
    session = await _session_manager.get_or_create(req.session_id, req.task)
    timings["session_ms"] = (time.perf_counter() - t0) * 1000

    if session.status != "RUNNING":
        return InferResponse(
            session_id=req.session_id,
            status=session.status.lower(),
            actions=[],
            checkpoint=True,
            reason=f"Session is {session.status}",
            timings=timings if _timings_enabled else None,
        )

    current_state_hash = hash_browser_state(req.browser_state.model_dump())
    previous_state_hash = session.last_browser_state_hash

    t1 = time.perf_counter()
    validation_results: list[dict[str, Any]] = []
    if session.last_action_batch:
        validation_results = _state_validator.validate_transition(
            previous_state=None,
            current_state=req.browser_state,
            previous_actions=session.last_action_batch,
            execution_results=req.execution_results,
        )
    timings["validation_ms"] = (time.perf_counter() - t1) * 1000

    t2 = time.perf_counter()
    _workflow_manager.update_after_execution(
        session=session,
        previous_browser_state_hash=previous_state_hash,
        current_browser_state_hash=current_state_hash,
        action_batch=req.execution_results if req.execution_results else [],
        execution_results=req.execution_results,
        validation_results=validation_results,
    )

    if _workflow_manager.detect_loop(session):
        _workflow_manager.mark_blocked(session, "Loop detected: repeated browser state")
        await _session_manager.save(session)
        return InferResponse(
            session_id=req.session_id,
            status="blocked",
            actions=[],
            checkpoint=True,
            reason="Loop detected: same browser state repeated. Please refresh the page.",
            timings=timings if _timings_enabled else None,
        )

    if not _workflow_manager.should_continue(session):
        await _session_manager.save(session)
        return InferResponse(
            session_id=req.session_id,
            status=session.status.lower(),
            actions=[],
            checkpoint=True,
            reason=session.summary or f"Session {session.status}",
            timings=timings if _timings_enabled else None,
        )
    timings["workflow_ms"] = (time.perf_counter() - t2) * 1000

    t3 = time.perf_counter()
    prompt = _prompt_builder.build(
        task=req.task or session.task,
        session_summary=session.summary,
        phase=session.phase,
        browser_state=req.browser_state,
        previous_actions=session.last_action_batch,
        validation_results=validation_results,
        execution_results=req.execution_results,
    )
    timings["prompt_ms"] = (time.perf_counter() - t3) * 1000

    image = None
    if req.screenshot and req.screenshot.data:
        try:
            image = _vlm_engine.decode_image(req.screenshot.data, req.screenshot.mime_type)
        except Exception as e:
            logger.warning("Failed to decode screenshot: %s", e)

    t4 = time.perf_counter()
    try:
        vlm_output = _vlm_engine.infer(image, prompt)
    except Exception as e:
        logger.error("VLM inference failed: %s", e)
        return InferResponse(
            session_id=req.session_id,
            status="error",
            actions=[],
            checkpoint=True,
            reason=f"VLM inference failed: {str(e)[:200]}",
            timings=timings if _timings_enabled else None,
        )
    timings["vlm_ms"] = (time.perf_counter() - t4) * 1000

    vlm_status = vlm_output.get("status", "blocked")
    vlm_actions = vlm_output.get("actions", [])
    vlm_phase = vlm_output.get("phase", session.phase)
    vlm_reason = vlm_output.get("reason", "")
    vlm_checkpoint = vlm_output.get("checkpoint", False)
    if not isinstance(vlm_checkpoint, bool):
        vlm_checkpoint = str(vlm_checkpoint).lower() in ("true", "1", "yes")

    if vlm_status == "done":
        _workflow_manager.mark_completed(session)
        await _session_manager.save(session)
        return InferResponse(
            session_id=req.session_id,
            status="done",
            actions=[],
            checkpoint=True,
            reason=vlm_reason or "Task completed",
            timings=timings if _timings_enabled else None,
        )

    t5 = time.perf_counter()
    valid_actions, validation_errors = _action_validator.validate(
        vlm_actions, req.browser_state
    )
    timings["validation_output_ms"] = (time.perf_counter() - t5) * 1000

    if validation_errors:
        logger.warning(
            "Action validation errors for session %s: %s",
            req.session_id,
            validation_errors,
        )

    if not valid_actions and vlm_status == "continue":
        _workflow_manager.update_summary(session, vlm_phase, vlm_reason, [])
        session.last_action_batch = []
        await _session_manager.save(session)
        return InferResponse(
            session_id=req.session_id,
            status="continue",
            actions=[],
            checkpoint=True,
            reason="No valid actions produced. " + "; ".join(validation_errors[:3]),
            timings=timings if _timings_enabled else None,
        )

    _workflow_manager.update_summary(session, vlm_phase, vlm_reason, valid_actions)
    session.last_action_batch = valid_actions
    await _session_manager.save(session)

    timings["total_ms"] = (time.perf_counter() - total_start) * 1000

    log_request(
        logger,
        session_id=req.session_id,
        page_url=req.browser_state.page.url or req.browser_state.page.title,
        element_count=len(req.browser_state.elements),
        action_count=len(valid_actions),
        phase=vlm_phase,
        latency_ms=timings["total_ms"],
    )

    return InferResponse(
        session_id=req.session_id,
        status=vlm_status if vlm_status in ("continue", "done", "blocked") else "continue",
        actions=valid_actions,
        checkpoint=vlm_checkpoint,
        reason=vlm_reason,
        timings=timings if _timings_enabled else None,
    )
