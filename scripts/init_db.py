"""
Initialize Supabase PostgreSQL tables for BrowserAuto backend.

Usage:
    python -m scripts.init_db

Requires DATABASE_URL in .env or environment.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv

load_dotenv(_root / ".env")

STATEMENTS = [
    # ── sessions ──
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        data JSONB NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions (updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions ((data->>'status'))",

    # ── action_history ──
    """
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_action_history_session ON action_history (session_id, step_index DESC)",

    # ── workflow_state ──
    """
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
    """,

    # ── page_visits ──
    """
    CREATE TABLE IF NOT EXISTS page_visits (
        id BIGSERIAL PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        url TEXT NOT NULL,
        title TEXT DEFAULT '',
        step_index INTEGER,
        visited_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_page_visits_session ON page_visits (session_id, visited_at DESC)",
]


async def init_database() -> None:
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        print("ERROR: DATABASE_URL not set. Check your .env file.")
        sys.exit(1)

    host = dsn.split("@")[1].split("/")[0] if "@" in dsn else "unknown"
    print(f"Connecting to Supabase PostgreSQL at {host}...")

    try:
        import asyncpg
    except ImportError:
        print("ERROR: asyncpg not installed. Run: pip install asyncpg")
        sys.exit(1)

    conn = await asyncpg.connect(dsn)
    try:
        print("Connected. Running migrations...\n")

        for i, stmt in enumerate(STATEMENTS, 1):
            label = stmt.strip().split("\n")[0][:55].strip()
            try:
                await conn.execute(stmt)
                print(f"  [{i:2d}] OK   {label}")
            except Exception as e:
                print(f"  [{i:2d}] FAIL {label}")
                print(f"        {e}")

        print("\nVerifying tables...")
        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
        )
        for row in rows:
            print(f"  - {row['table_name']}")

        print(f"\nDone. {len(rows)} tables found.")
    finally:
        await conn.close()


def main() -> None:
    asyncio.run(init_database())


if __name__ == "__main__":
    main()
