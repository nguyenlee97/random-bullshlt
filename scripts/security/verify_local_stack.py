"""Black-box security checks for the local Compose stack (no model calls)."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DIRECT = os.getenv("AGENT_DIRECT_URL", "http://127.0.0.1:8080")
PROXY = os.getenv("AGENT_PROXY_URL", "http://127.0.0.1:5175/agent")
LOCAL_KEY = os.getenv("AGENT_API_KEY", "local-dev-agent-key")


def request(method: str, url: str, payload=None, headers=None):
    body = json.dumps(payload).encode() if payload is not None else None
    final_headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=final_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def require(label: str, condition: bool, detail: str = ""):
    if not condition:
        raise AssertionError(f"{label}: FAIL {detail}")
    print(f"{label}: PASS")


def main() -> int:
    status, _, _ = request("GET", f"{DIRECT}/health")
    require("health", status == 200, f"status={status}")

    boot = {"message": "", "step": -1, "session_id": "security_boot"}
    status, _, _ = request("POST", f"{DIRECT}/api/agent/chat", boot)
    require("direct agent requires server credential", status == 401, f"status={status}")

    status, _, _ = request("POST", f"{PROXY}/api/agent/chat", boot)
    require("same-origin frontend proxy injects credential", status == 200, f"status={status}")

    huge = {"message": "x" * (2 * 1024 * 1024 + 1), "step": 0, "session_id": "too_big"}
    status, _, _ = request(
        "POST", f"{DIRECT}/api/agent/chat", huge, {"X-API-Key": LOCAL_KEY}
    )
    require("direct request-size limit", status == 413, f"status={status}")
    status, _, _ = request("POST", f"{PROXY}/api/agent/chat", huge)
    require("proxy request-size limit", status == 413, f"status={status}")

    status, headers, _ = request(
        "OPTIONS",
        f"{DIRECT}/api/agent/chat",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    allowed_origin = next(
        (value for key, value in headers.items() if key.lower() == "access-control-allow-origin"),
        None,
    )
    require("untrusted CORS origin rejected", allowed_origin is None)

    session_id = f"security_delete_{int(time.time())}"
    preference = {
        "session_id": session_id,
        # The default is guided. Use a real state change so deletion must also
        # remove the append-only workspace event created by this mutation.
        "experience_mode": "autopilot",
        "base_revision": 0,
        "idempotency_key": session_id,
    }
    status, _, body = request(
        "POST", f"{PROXY}/api/agent/workspace/preferences", preference
    )
    require("session fixture created", status == 200, f"status={status} body={body[:120]!r}")
    status, _, body = request("DELETE", f"{PROXY}/api/agent/sessions/{session_id}")
    deleted = json.loads(body or b"{}")
    require(
        "session deletion removes workspace",
        status == 200 and deleted.get("deleted", {}).get("campaign_workspaces", 0) >= 1,
        f"status={status}",
    )
    require(
        "session deletion removes append-only workspace events",
        deleted.get("deleted", {}).get("workspace_events", 0) >= 1,
        f"deleted={deleted.get('deleted', {})}",
    )

    statuses = []
    for index in range(35):
        rate_boot = {**boot, "session_id": f"security_rate_{index}"}
        status, _, _ = request("POST", f"{PROXY}/api/agent/chat", rate_boot)
        statuses.append(status)
        if status == 429:
            break
    require(
        "chat rate limit",
        429 in statuses and all(code in (200, 429) for code in statuses),
        f"statuses={statuses}",
    )

    print("Local security boundary suite: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Local security boundary suite: FAIL ({error})", file=sys.stderr)
        raise
