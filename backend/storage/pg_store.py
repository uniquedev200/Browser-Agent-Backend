from __future__ import annotations

import json
import logging
from typing import Any, Optional

from backend.schemas.session import SessionData
from backend.storage.base import SessionStore

logger = logging.getLogger("browserauto.storage.pg")


class PGSessionStore(SessionStore):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: Any = None

    async def connect(self) -> None:
        try:
            import asyncpg
        except ImportError:
            raise RuntimeError(
                "asyncpg is required for PostgreSQL storage. "
                "Install it with: pip install asyncpg"
            )
        self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
        await self._ensure_tables()

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def _ensure_tables(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
                    ON sessions (updated_at DESC)
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS action_history (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    step_index INTEGER NOT NULL,
                    action_batch JSONB NOT NULL,
                    validation_results JSONB DEFAULT '[]'::jsonb,
                    vlm_output JSONB DEFAULT '{}'::jsonb,
                    state_hash_before TEXT,
                    state_hash_after TEXT,
                    latency_ms REAL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_action_history_session
                    ON action_history (session_id, step_index DESC)
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_state (
                    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
                    phase TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    step_index INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    last_state_hash TEXT DEFAULT '',
                    previous_state_hash TEXT DEFAULT '',
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS page_visits (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    url TEXT NOT NULL,
                    title TEXT DEFAULT '',
                    step_index INTEGER,
                    visited_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_page_visits_session
                    ON page_visits (session_id, visited_at DESC)
            """)

    # ── SessionStore interface ──────────────────────────────

    async def create(self, session: SessionData) -> SessionData:
        session.ensure_created()
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO sessions (session_id, data, created_at, updated_at)
                    VALUES ($1, $2::jsonb, NOW(), NOW())
                    """,
                    session.session_id,
                    json.dumps(session.model_dump()),
                )
                await conn.execute(
                    """
                    INSERT INTO workflow_state (session_id, phase, summary, step_index, retry_count)
                    VALUES ($1, '', '', 0, 0)
                    ON CONFLICT (session_id) DO NOTHING
                    """,
                    session.session_id,
                )
        return session

    async def get(self, session_id: str) -> Optional[SessionData]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM sessions WHERE session_id = $1",
                session_id,
            )
        if row is None:
            return None
        return SessionData.model_validate(json.loads(row["data"]))

    async def update(self, session: SessionData) -> SessionData:
        session.touch_updated()
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE sessions
                    SET data = $2::jsonb, updated_at = NOW()
                    WHERE session_id = $1
                    """,
                    session.session_id,
                    json.dumps(session.model_dump()),
                )
                await conn.execute(
                    """
                    UPDATE workflow_state
                    SET phase = $2,
                        summary = $3,
                        step_index = $4,
                        retry_count = $5,
                        last_state_hash = $6,
                        previous_state_hash = $7,
                        updated_at = NOW()
                    WHERE session_id = $1
                    """,
                    session.session_id,
                    session.phase,
                    session.summary,
                    session.step_index,
                    session.retry_count,
                    session.last_browser_state_hash,
                    session.previous_browser_state_hash,
                )
        return session

    async def delete(self, session_id: str) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM sessions WHERE session_id = $1",
                session_id,
            )
        return result.endswith("1")

    async def list_sessions(self) -> list[SessionData]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT data FROM sessions")
        return [SessionData.model_validate(json.loads(r["data"])) for r in rows]

    # ── Action history ──────────────────────────────────────

    async def record_action(
        self,
        session_id: str,
        step_index: int,
        action_batch: list[dict[str, Any]],
        validation_results: list[dict[str, Any]] | None = None,
        vlm_output: dict[str, Any] | None = None,
        state_hash_before: str = "",
        state_hash_after: str = "",
        latency_ms: float = 0.0,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO action_history
                    (session_id, step_index, action_batch, validation_results,
                     vlm_output, state_hash_before, state_hash_after, latency_ms)
                VALUES ($1, $2, $3::jsonb, $4::jsonb, $5::jsonb, $6, $7, $8)
                """,
                session_id,
                step_index,
                json.dumps(action_batch),
                json.dumps(validation_results or []),
                json.dumps(vlm_output or {}),
                state_hash_before,
                state_hash_after,
                latency_ms,
            )

    async def get_action_history(
        self, session_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT step_index, action_batch, validation_results,
                       state_hash_before, state_hash_after, latency_ms, created_at
                FROM action_history
                WHERE session_id = $1
                ORDER BY step_index DESC
                LIMIT $2
                """,
                session_id,
                limit,
            )
        return [
            {
                "step_index": r["step_index"],
                "action_batch": json.loads(r["action_batch"]),
                "validation_results": json.loads(r["validation_results"]),
                "state_hash_before": r["state_hash_before"],
                "state_hash_after": r["state_hash_after"],
                "latency_ms": r["latency_ms"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

    # ── Page visits ─────────────────────────────────────────

    async def record_page_visit(
        self,
        session_id: str,
        url: str,
        title: str = "",
        step_index: int = 0,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO page_visits (session_id, url, title, step_index)
                VALUES ($1, $2, $3, $4)
                """,
                session_id,
                url,
                title,
                step_index,
            )

    async def get_page_visits(self, session_id: str) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT url, title, step_index, visited_at
                FROM page_visits
                WHERE session_id = $1
                ORDER BY visited_at ASC
                """,
                session_id,
            )
        return [
            {
                "url": r["url"],
                "title": r["title"],
                "step_index": r["step_index"],
                "visited_at": r["visited_at"].isoformat() if r["visited_at"] else None,
            }
            for r in rows
        ]
