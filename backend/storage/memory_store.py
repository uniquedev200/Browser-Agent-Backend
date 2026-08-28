from __future__ import annotations

from typing import Optional

from backend.schemas.session import SessionData
from backend.storage.base import SessionStore


class MemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._store: dict[str, SessionData] = {}

    async def create(self, session: SessionData) -> SessionData:
        session.ensure_created()
        self._store[session.session_id] = session.model_copy(deep=True)
        return session

    async def get(self, session_id: str) -> Optional[SessionData]:
        session = self._store.get(session_id)
        if session is not None:
            return session.model_copy(deep=True)
        return None

    async def update(self, session: SessionData) -> SessionData:
        session.touch_updated()
        self._store[session.session_id] = session.model_copy(deep=True)
        return session

    async def delete(self, session_id: str) -> bool:
        if session_id in self._store:
            del self._store[session_id]
            return True
        return False

    async def list_sessions(self) -> list[SessionData]:
        return [s.model_copy(deep=True) for s in self._store.values()]
