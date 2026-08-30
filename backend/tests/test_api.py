from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.actions.action_validator import ActionValidator
from backend.api.routes import init_routes, router
from backend.main import app
from backend.prompts.prompt_builder import PromptBuilder
from backend.session.session_manager import SessionManager
from backend.storage.memory_store import MemorySessionStore
from backend.validation.browser_state_validator import BrowserStateValidator
from backend.workflow.workflow_manager import WorkflowManager


class FakeVLMEngine:
    def load(self):
        pass

    def decode_image(self, image_data, mime_type="image/png"):
        return None

    def infer(self, image, prompt):
        return {
            "status": "continue",
            "phase": "test",
            "actions": [
                {"action_id": "a1", "type": "fill", "target": "el_1", "value": "<PERSON>"}
            ],
            "checkpoint": True,
            "reason": "Test fill action",
        }


@pytest_asyncio.fixture(autouse=True)
async def setup_routes():
    store = MemorySessionStore()
    sm = SessionManager(store)
    wm = WorkflowManager()
    sv = BrowserStateValidator()
    pb = PromptBuilder()
    vlm = FakeVLMEngine()
    av = ActionValidator()

    init_routes(sm, wm, sv, pb, vlm, av, debug_timings=True)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_session(client):
    resp = await client.post("/api/v1/session", json={"session_id": "sess_test_1", "task": "Test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "sess_test_1"
    assert data["status"] == "RUNNING"


@pytest.mark.asyncio
async def test_get_session(client):
    await client.post("/api/v1/session", json={"session_id": "sess_test_2", "task": "Get me"})
    resp = await client.get("/api/v1/session/sess_test_2")
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "sess_test_2"


@pytest.mark.asyncio
async def test_get_nonexistent_session(client):
    resp = await client.get("/api/v1/session/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_session(client):
    await client.post("/api/v1/session", json={"session_id": "sess_del", "task": "Delete"})
    resp = await client.delete("/api/v1/session/sess_del")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_infer_basic(client):
    request_body = {
        "session_id": "sess_infer_1",
        "task": "Complete the registration form",
        "browser_state": {
            "page": {
                "title": "Registration",
                "url": "https://example.com/register",
                "viewport": {"width": 1440, "height": 900},
                "scroll": {"x": 0, "y": 0},
            },
            "elements": [
                {
                    "element_id": "el_1",
                    "role": "textbox",
                    "label": "Full Name",
                    "value": "",
                    "bbox": [100, 150, 300, 40],
                    "visible": True,
                    "enabled": True,
                },
                {
                    "element_id": "el_2",
                    "role": "button",
                    "text": "Submit",
                    "bbox": [100, 300, 120, 40],
                    "visible": True,
                    "enabled": True,
                },
            ],
        },
        "execution_results": [],
    }
    resp = await client.post("/api/v1/infer", json=request_body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "sess_infer_1"
    assert data["status"] == "continue"
    assert len(data["actions"]) > 0
    assert data["timings"] is not None


@pytest.mark.asyncio
async def test_infer_session_resumption(client):
    body = {
        "session_id": "sess_resume",
        "task": "Apply for internship",
        "browser_state": {
            "page": {"title": "Page 1", "url": "https://example.com/p1"},
            "elements": [
                {"element_id": "el_1", "role": "textbox", "label": "Name", "enabled": True},
            ],
        },
    }
    resp1 = await client.post("/api/v1/infer", json=body)
    assert resp1.status_code == 200

    body["browser_state"]["page"]["title"] = "Page 2"
    body["browser_state"]["page"]["url"] = "https://example.com/p2"
    resp2 = await client.post("/api/v1/infer", json=body)
    assert resp2.status_code == 200
    assert resp2.json()["session_id"] == "sess_resume"


@pytest.mark.asyncio
async def test_infer_with_timings(client):
    body = {
        "session_id": "sess_timing",
        "task": "Test timings",
        "browser_state": {
            "page": {"title": "Test", "url": "https://example.com"},
            "elements": [],
        },
    }
    resp = await client.post("/api/v1/infer", json=body)
    assert resp.status_code == 200
    timings = resp.json()["timings"]
    assert "total_ms" in timings
    assert "session_ms" in timings
