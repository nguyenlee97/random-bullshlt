"""Reset namespaced local demo state without touching non-demo data."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse

from pymongo import MongoClient


def _namespace(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    if not cleaned:
        raise ValueError("namespace must contain letters or numbers")
    return cleaned[:32]


def _walk_urls(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"url", "fileUrl", "dataUrl"} and isinstance(child, str):
                yield child
            else:
                yield from _walk_urls(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_urls(child)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default=os.getenv("DEMO_NAMESPACE", "local-demo"))
    parser.add_argument("--mongo-uri", default=os.getenv("DEMO_MONGODB_URI", "mongodb://127.0.0.1:27017"))
    parser.add_argument("--agent-db", default=os.getenv("MONGODB_DB", "camp_ads"))
    parser.add_argument("--backend-db", default=os.getenv("BACKEND_MONGODB_DB", "adspilot"))
    parser.add_argument("--uploads", default="backend/uploads")
    parser.add_argument("--include-orders", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Perform deletion; otherwise print a dry-run plan")
    args = parser.parse_args()

    namespace = _namespace(args.namespace)
    prefix = f"sess_{namespace}_"
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[args.agent_db]
    session_ids = set(db.agent_sessions.distinct("_id", {"_id": {"$regex": f"^{re.escape(prefix)}"}}))
    session_ids.update(db.campaign_workspaces.distinct("session_id", {"session_id": {"$regex": f"^{re.escape(prefix)}"}}))
    session_ids = sorted(item for item in session_ids if isinstance(item, str) and item.startswith(prefix))

    workspaces = list(db.campaign_workspaces.find({"session_id": {"$in": session_ids}}))
    workspace_ids = [item.get("_id") for item in workspaces if item.get("_id")]
    uploads_root = Path(args.uploads).resolve()
    files = set()
    for workspace in workspaces:
        for url in _walk_urls(workspace.get("artifacts", {})):
            name = Path(urlparse(url).path).name
            if not name:
                continue
            candidate = (uploads_root / name).resolve()
            if candidate.parent == uploads_root and candidate.exists() and candidate.is_file():
                files.add(candidate)

    plan = {
        "namespace": namespace,
        "session_prefix": prefix,
        "sessions": len(session_ids),
        "creative_files": len(files),
        "orders_included": bool(args.include_orders),
        "mode": "apply" if args.apply else "dry-run",
    }
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        print("Dry run only. Add --apply after checking the namespace.")
        return 0

    deleted: dict[str, int] = {}
    run_ids = db.agent_runs.distinct("run_id", {"session_id": {"$in": session_ids}})
    filters = {
        "agent_sessions": {"_id": {"$in": session_ids}},
        "agent_logs": {"session_id": {"$in": session_ids}},
        "campaign_workspaces": {"session_id": {"$in": session_ids}},
        "workspace_proposals": {"session_id": {"$in": session_ids}},
        "workspace_events": {"$or": [
            {"session_id": {"$in": session_ids}},
            {"workspace_id": {"$in": workspace_ids}},
        ]},
        "creative_intel_jobs": {"session_id": {"$in": session_ids}},
        "agent_runs": {"session_id": {"$in": session_ids}},
        "agent_tasks": {"run_id": {"$in": run_ids}},
        "agent_run_events": {"run_id": {"$in": run_ids}},
        "graph_checkpoints": {"thread_id": {"$in": session_ids + [f"{sid}:auto" for sid in session_ids]}},
        "checkpoint_writes": {"thread_id": {"$in": session_ids + [f"{sid}:auto" for sid in session_ids]}},
    }
    for collection, query in filters.items():
        deleted[collection] = db[collection].delete_many(query).deleted_count
    removed_files = 0
    for path in files:
        path.unlink(missing_ok=True)
        removed_files += 1
    deleted["creative_files"] = removed_files

    if args.include_orders:
        backend = client[args.backend_db]
        key_pattern = {"$regex": re.escape(namespace), "$options": "i"}
        campaigns = list(backend.campaigns.find({"idempotencyKey": key_pattern}, {"_id": 1}))
        campaign_ids = [item["_id"] for item in campaigns]
        campaign_strings = [str(item) for item in campaign_ids]
        deleted["campaigns"] = backend.campaigns.delete_many({"_id": {"$in": campaign_ids}}).deleted_count
        deleted["report_analyses"] = backend.report_analyses.delete_many({"campaignId": {"$in": campaign_strings}}).deleted_count
        deleted["analytic_records"] = backend.analytic_records.delete_many({"campaignId": {"$in": campaign_strings}}).deleted_count

    plan["deleted"] = deleted
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
