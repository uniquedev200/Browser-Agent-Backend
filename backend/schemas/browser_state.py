from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class Viewport(BaseModel):
    """Browser viewport dimensions."""

    width: int = Field(default=1440, description="Viewport width in pixels")
    height: int = Field(default=900, description="Viewport height in pixels")


class ScrollPosition(BaseModel):
    """Current scroll position."""

    x: int = Field(default=0, description="Horizontal scroll position")
    y: int = Field(default=0, description="Vertical scroll position")


class PageMetadata(BaseModel):
    """Page-level metadata."""

    title: str = Field(default="", description="Page title")
    url: str = Field(default="", description="Full page URL")
    domain: str = Field(default="", description="Page domain")
    viewport: Viewport = Field(default_factory=Viewport, description="Viewport dimensions")
    scroll: ScrollPosition = Field(default_factory=ScrollPosition, description="Scroll position")


class ElementState(BaseModel):
    """A single interactable or visible element on the page."""

    element_id: str = Field(description="Unique element identifier")
    role: str = Field(default="", description="ARIA role (textbox, button, checkbox, etc.)")
    type: str = Field(default="", description="Input type (text, email, tel, etc.)")
    tag: str = Field(default="", description="HTML tag name")
    text: str = Field(default="", description="Visible text content")
    label: str = Field(default="", description="Label text")
    placeholder: str = Field(default="", description="Placeholder text")
    value: str = Field(default="", description="Current value (may be a semantic placeholder)")
    bbox: list[int] = Field(default_factory=list, description="Bounding box [x, y, width, height]")
    visible: bool = Field(default=True, description="Whether element is visible")
    enabled: bool = Field(default=True, description="Whether element is interactable")
    focused: bool = Field(default=False, description="Whether element has focus")
    checked: Optional[bool] = Field(default=None, description="Checkbox state")
    expanded: Optional[bool] = Field(default=None, description="Expandable state")
    selected: Optional[bool] = Field(default=None, description="Selection state")
    disabled: Optional[bool] = Field(default=None, description="Disabled state")


class BrowserState(BaseModel):
    """Complete normalized browser state from the extension."""

    page: PageMetadata = Field(default_factory=PageMetadata, description="Page metadata")
    elements: list[ElementState] = Field(
        default_factory=list,
        description="List of visible/interactable elements on the page",
    )
