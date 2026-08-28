from __future__ import annotations

import abc
from typing import Any, Optional

from backend.schemas.session import SessionData


class SessionStore(abc.ABC):
    @abc.abstractmethod
    async def create(self, session: SessionData) -> SessionData:
        ...

    @abc.abstractmethod
    async def get(self, session_id: str) -> Optional[SessionData]:
        ...

    @abc.abstractmethod
    async def update(self, session: SessionData) -> SessionData:
        ...

    @abc.abstractmethod
    async def delete(self, session_id: str) -> bool:
        ...

    @abc.abstractmethod
    async def list_sessions(self) -> list[SessionData]:
        ...
