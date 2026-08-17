"""Prewarm local demo dependencies and optionally the online audience path."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import os
import time

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5175")
    parser.add_argument("--backend", default="http://127.0.0.1:3000")
    parser.add_argument("--qdrant", default="http://127.0.0.1:6333")
    parser.add_argument("--namespace", default=os.getenv("DEMO_NAMESPACE", "local-demo"))
    parser.add_argument("--online", action="store_true", help="Also warm model-backed audience recommendation")
    args = parser.parse_args()
    session_id = f"sess_{args.namespace}_prewarm_{int(time.time())}"
    checks = {}
    with httpx.Client(timeout=180) as client:
        targets = {
            "frontend": f"{args.base}/healthz",
            "agent_ready": f"{args.base}/agent/ready",
            "backend": f"{args.backend}/api/health",
            "catalog": f"{args.backend}/api/dmp/attributes",
            "qdrant": f"{args.qdrant}/collections",
            "docs": f"{args.base}/tech-docs.html",
        }
        for name, url in targets.items():
            response = client.get(url)
            checks[name] = {"status": response.status_code, "ok": response.is_success}
            response.raise_for_status()

        boot = client.post(f"{args.base}/agent/api/agent/chat", json={
            "session_id": session_id, "step": -1, "message": "",
        })
        boot.raise_for_status()
        checks["boot"] = {"status": boot.status_code, "tool": boot.json().get("meta", {}).get("tool")}

        if args.online:
            workspace = client.get(f"{args.base}/agent/api/agent/workspace", params={"session_id": session_id}).json()
            start = date.today() + timedelta(days=14)
            end = start + timedelta(days=14)
            committed = client.post(f"{args.base}/agent/api/agent/commit-workspace", json={
                "session_id": session_id, "field": "brief",
                "value": {
                    "brand": "Advertising Agent Prewarm", "objective": "awareness",
                    "budget": 10, "startDate": start.isoformat(), "endDate": end.isoformat(),
                    "notes": "Người dùng trẻ quan tâm công nghệ tại Hà Nội và TP.HCM",
                },
                "base_revision": workspace["revision"], "actor": "demo_prewarm",
                "idempotency_key": f"{session_id}:brief",
            })
            committed.raise_for_status()
            audience = client.get(
                f"{args.base}/agent/api/agent/dmp-recommend",
                params={"session_id": session_id},
            )
            audience.raise_for_status()
            checks["online_audience"] = {
                "status": audience.status_code,
                "recommendations": len(audience.json().get("recommendations", [])),
            }

        cleanup = client.delete(f"{args.base}/agent/api/agent/sessions/{session_id}")
        checks["cleanup"] = {"status": cleanup.status_code, "ok": cleanup.is_success}
    print(json.dumps({"session_id": session_id, "checks": checks, "result": "PASS"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
