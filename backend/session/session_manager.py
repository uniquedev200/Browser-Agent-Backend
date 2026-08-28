from __future__ import annotations

import logging
from typing import Optional

from backend.schemas.session import SessionData
from backend.storage.base import SessionStore

logger = logging.getLogger("browserauto.session")


class SessionManager:
    def __init__(self, store: SessionStore) -> None:
        self._store = store

    async def get_or_create(self, session_id: str, task: str = "") -> SessionData:
        session = await self._store.get(session_id)
        if session is not None:
            logger.debug("Loaded existing session %s", session_id)
            return session
        session = SessionData(session_id=session_id, task=task)
        await self._store.create(session)
        logger.debug("Created new session %s", session_id)
        return session

    async def get(self, session_id: str) -> Optional[SessionData]:
        return await self._store.get(session_id)

    async def save(self, session: SessionData) -> None:
        await self._store.update(session)

    async def delete(self, session_id: str) -> bool:
        return await self._store.delete(session_id)
