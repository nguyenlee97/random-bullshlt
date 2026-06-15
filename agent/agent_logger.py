"""
Structured agent logger.

Every call writes to:
  1. stdout  → visible in `pm2 logs` / `docker logs` / VPS console
  2. MongoDB  → queryable via GET /api/agent/logs/{session_id}

Usage:
    from agent_logger import alog
    await alog(session_id, "llm_call", {"tool": "get_audience_list", "duration_ms": 3200})
"""
import time
from datetime import datetime, timezone
from session import log_event

# ANSI colours for pm2 / terminal readability
_C = {
    "reset":   "\033[0m",
    "bold":    "\033[1m",
    "cyan":    "\033[36m",
    "green":   "\033[32m",
    "yellow":  "\033[33m",
    "red":     "\033[31m",
    "magenta": "\033[35m",
    "blue":    "\033[34m",
    "gray":    "\033[90m",
}

_TAG_COLOR = {
    "request":        "cyan",
    "llm_call_start": "blue",
    "llm_call_done":  "green",
    "tool_call":      "magenta",
    "tool_result":    "magenta",
    "fallback":       "yellow",
    "confirm":        "green",
    "reply":          "green",
    "error":          "red",
    "warn":           "yellow",
    "info":           "gray",
}


def _fmt(event_type: str, data: dict, session_id: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    color = _C.get(_TAG_COLOR.get(event_type, "gray"), "")
    reset = _C["reset"]
    bold  = _C["bold"]
    sid   = session_id[-8:]  # last 8 chars only

    # Build compact one-line summary
    parts = [f"{color}{bold}[{event_type.upper()}]{reset}",
             f"{_C['gray']}[{sid}] {ts}{reset}"]

    for k, v in data.items():
        if isinstance(v, str) and len(v) > 120:
            v = v[:120] + "…"
        elif isinstance(v, list) and len(v) > 5:
            v = v[:5] + [f"…+{len(v)-5}"]
        parts.append(f"{k}={v!r}")

    return "  ".join(parts)


async def alog(session_id: str, event_type: str, data: dict) -> None:
    """Log to stdout AND MongoDB."""
    print(_fmt(event_type, data, session_id), flush=True)
    await log_event(session_id, event_type, data)
