"""Black-hole the configured primary endpoint and verify breaker timing."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = Path("/app") if Path("/app/llm.py").exists() else ROOT / "agent"
sys.path.insert(0, str(AGENT_DIR))

import llm  # noqa: E402


def main() -> int:
    observations = []
    kwargs = {
        "model": llm.config.LLM_MODEL,
        "messages": [{"role": "user", "content": "provider health drill"}],
        "max_tokens": 1,
    }
    for attempt in range(2):
        started = time.perf_counter()
        try:
            llm._create_completion(kwargs)
            observations.append({"attempt": attempt + 1, "result": "unexpected_success"})
        except Exception as error:
            observations.append({
                "attempt": attempt + 1,
                "error_type": type(error).__name__,
                "duration_s": round(time.perf_counter() - started, 3),
            })

    passed = bool(
        len(observations) == 2
        and observations[0].get("error_type")
        and observations[1].get("error_type") == "CircuitOpenError"
        and observations[1].get("duration_s", 99) < 0.1
        and llm._fallback_client is None
    )
    print(json.dumps({
        "fallback_policy": "disabled_for_classification",
        "observations": observations,
        "passed": passed,
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
