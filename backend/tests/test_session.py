from __future__ import annotations

import pytest
import pytest_asyncio

from backend.schemas.session import SessionData
from backend.session.session_manager import SessionManager
from backend.storage.memory_store import MemorySessionStore


@pytest_asyncio.fixture
async def store():
    return MemorySessionStore()


@pytest_asyncio.fixture
async def session_manager(store):
    return SessionManager(store)


@pytest.mark.asyncio
async def test_create_session(session_manager):
    session = await session_manager.get_or_create("sess_001", "Test task")
    assert session.session_id == "sess_001"
    assert session.task == "Test task"
    assert session.status == "RUNNING"
    assert session.step_index == 0
    assert session.retry_count == 0


@pytest.mark.asyncio
async def test_get_existing_session(session_manager):
    s1 = await session_manager.get_or_create("sess_002", "Task A")
    s2 = await session_manager.get_or_create("sess_002", "Task B")
    assert s1.session_id == s2.session_id
    assert s2.task == "Task A"


@pytest.mark.asyncio
async def test_session_isolation(session_manager):
    s1 = await session_manager.get_or_create("sess_A", "Task A")
    s2 = await session_manager.get_or_create("sess_B", "Task B")

    s1.summary = "User A summary"
    await session_manager.save(s1)

    loaded = await session_manager.get("sess_B")
    assert loaded.summary != "User A summary"


@pytest.mark.asyncio
async def test_delete_session(session_manager):
    await session_manager.get_or_create("sess_del", "Delete me")
    deleted = await session_manager.delete("sess_del")
    assert deleted is True

    not_found = await session_manager.get("sess_del")
    assert not_found is None


@pytest.mark.asyncio
async def test_delete_nonexistent_session(session_manager):
    deleted = await session_manager.delete("nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_update_session(session_manager):
    session = await session_manager.get_or_create("sess_upd", "Original")
    session.summary = "Updated summary"
    session.phase = "education"
    session.step_index = 3
    await session_manager.save(session)

    loaded = await session_manager.get("sess_upd")
    assert loaded.summary == "Updated summary"
    assert loaded.phase == "education"
    assert loaded.step_index == 3


@pytest.mark.asyncio
async def test_session_timestamps(session_manager):
    session = await session_manager.get_or_create("sess_time", "Timestamp test")
    assert session.created_at != ""
    assert session.updated_at != ""


@pytest.mark.asyncio
async def test_multiple_users_isolation(session_manager):
    sessions = {}
    for i in range(10):
        sid = f"sess_user_{i}"
        s = await session_manager.get_or_create(sid, f"Task {i}")
        s.summary = f"Summary for user {i}"
        await session_manager.save(s)
        sessions[sid] = s

    for i in range(10):
        sid = f"sess_user_{i}"
        loaded = await session_manager.get(sid)
        assert loaded is not None
        assert loaded.summary == f"Summary for user {i}"

    for i in range(10):
        for j in range(i + 1, 10):
            sid_a = f"sess_user_{i}"
            sid_b = f"sess_user_{j}"
            assert sid_a != sid_b
