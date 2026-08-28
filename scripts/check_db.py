import asyncio, asyncpg, json, os
from dotenv import load_dotenv
load_dotenv(".env")

async def check():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))

    rows = await conn.fetch("SELECT session_id, data FROM sessions")
    print("=== Sessions in Supabase ===")
    for r in rows:
        d = json.loads(r["data"])
        print(f"  {d['session_id']}  status={d['status']}  phase={d['phase']}  steps={d['step_index']}")

    rows2 = await conn.fetch("SELECT session_id, phase, step_index, retry_count FROM workflow_state")
    print("\n=== Workflow State ===")
    for r in rows2:
        print(f"  {r['session_id']}  phase={r['phase']}  step={r['step_index']}  retries={r['retry_count']}")

    await conn.close()

asyncio.run(check())
