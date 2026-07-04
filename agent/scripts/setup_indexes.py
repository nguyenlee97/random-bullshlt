"""
One-shot index setup (Phase 0 A5) — safe to re-run (idempotent).

Creates:
  1. TTL index on agent_sessions.updated_at (SESSION_TTL_DAYS, default 30)
     — updated_at is already a UTC datetime set on every session write.
  2. TTL on api_logs.ts if that collection exists (90 days).

Note: the Campaign.idempotencyKey unique sparse index is created by Mongoose
automatically when the Node backend restarts (autoIndex). Verify with:
  mongosh "<uri>" --eval "db.campaigns.getIndexes()"

Run from agent/:  python scripts/setup_indexes.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from config import config  # noqa: E402

TTL_DAYS = int(getattr(config, "SESSION_TTL_DAYS", 30))


async def main():
    client = AsyncIOMotorClient(config.MONGODB_URI, serverSelectionTimeoutMS=8000)
    db = client[config.MONGODB_DB]
    await db.command("ping")
    print(f"Connected to {config.MONGODB_DB}")

    secs = TTL_DAYS * 86400
    # drop old TTL index if the expiry changed (Mongo can't alter TTL via createIndex)
    existing = {i["name"]: i async for i in db.agent_sessions.list_indexes()}
    if "updated_at_ttl" in existing and existing["updated_at_ttl"].get("expireAfterSeconds") != secs:
        await db.agent_sessions.drop_index("updated_at_ttl")
        print("dropped stale TTL index")
    await db.agent_sessions.create_index(
        "updated_at", name="updated_at_ttl", expireAfterSeconds=secs)
    print(f"✅ agent_sessions TTL: {TTL_DAYS} days on updated_at")

    if "api_logs" in await db.list_collection_names():
        await db.api_logs.create_index("ts", name="ts_ttl", expireAfterSeconds=90 * 86400)
        print("✅ api_logs TTL: 90 days on ts")

    for name, idx in [(i["name"], i) async for i in db.agent_sessions.list_indexes()]:
        print("  index:", name, idx.get("expireAfterSeconds", ""))


if __name__ == "__main__":
    asyncio.run(main())
