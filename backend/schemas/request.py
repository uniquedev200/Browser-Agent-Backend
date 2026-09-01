from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.schemas.browser_state import BrowserState


class ScreenshotData(BaseModel):
    """Sanitized screenshot from the browser extension."""

    mime_type: str = Field(default="image/png", description="Image MIME type")
    data: str = Field(description="Base64-encoded sanitized image")


class InferRequest(BaseModel):
    """Request to the main inference endpoint."""

    session_id: str = Field(description="Unique session identifier")
    task: str = Field(default="", description="User's task/goal description")
    browser_state: BrowserState = Field(
        default_factory=BrowserState,
        description="Normalized browser state with elements, page info, and viewport",
    )
    screenshot: Optional[ScreenshotData] = Field(
        default=None,
        description="Sanitized screenshot (privacy-filtered on client side)",
    )
    execution_results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Execution results from the previous action batch",
    )
    available_keys: list[str] = Field(
        default_factory=list,
        description="Key names from client vault (e.g., ['FullName', 'Email', 'Phone']). Server returns keys in actions, client decrypts locally.",
    )


class InferResponse(BaseModel):
    """Response from the inference endpoint."""

    session_id: str = Field(description="Session identifier")
    status: str = Field(
        description="Action status: 'continue', 'done', 'blocked', or 'error'"
    )
    actions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of structured actions for the browser to execute",
    )
    checkpoint: bool = Field(
        default=False,
        description="Whether the client should capture a new state after executing",
    )
    reason: str = Field(
        default="",
        description="VLM's reasoning for the action batch",
    )
    timings: Optional[dict[str, float]] = Field(
        default=None,
        description="Timing breakdown (only when DEBUG_TIMINGS=true)",
    )


class SessionCreateRequest(BaseModel):
    """Request to create or resume a session."""

    session_id: str = Field(description="Unique session identifier")
    task: str = Field(default="", description="User's task/goal description")


class SessionCreateResponse(BaseModel):
    """Response after creating a session."""

    session_id: str = Field(description="Session identifier")
    status: str = Field(description="Session status (e.g. 'RUNNING')")
    created_at: str = Field(description="ISO timestamp of creation")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="ok", description="Server health status")
