"""Find or remove append-only workspace events whose workspace was deleted."""
from __future__ import annotations

import argparse
import json
import os

from pymongo import MongoClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mongo-uri", default=os.getenv("DEMO_MONGODB_URI", "mongodb://127.0.0.1:27017"))
    parser.add_argument("--db", default=os.getenv("MONGODB_DB", "camp_ads"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[args.db]
    workspace_ids = set(db.campaign_workspaces.distinct("_id"))
    orphan_ids = [
        item["_id"] for item in db.workspace_events.find(
            {"workspace_id": {"$nin": list(workspace_ids)}}, {"_id": 1}
        )
    ]
    deleted = 0
    if args.apply and orphan_ids:
        deleted = db.workspace_events.delete_many({"_id": {"$in": orphan_ids}}).deleted_count
    print(json.dumps({
        "database": args.db,
        "orphan_workspace_events": len(orphan_ids),
        "deleted": deleted,
        "mode": "apply" if args.apply else "dry-run",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
