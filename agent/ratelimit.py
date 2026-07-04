"""
Rate limiting (Phase 0 A2) — SlowAPI, keyed on client IP.

Shared limiter instance: main.py registers it on the app; router.py decorates
the expensive endpoints. Limits are deliberately generous for the demo — the
goal is stopping scripted abuse of an open LLM endpoint, not throttling users.
"""
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

CHAT_LIMIT = "30/minute"          # POST /api/agent/chat — every call may hit the LLM
RECOMMEND_LIMIT = "10/minute"     # dmp-recommend / zones-recommend — heavy LLM calls
DEFAULT_LIMITS = ["120/minute"]   # everything else

# RATE_LIMIT_ENABLED=false in .env disables all limits — needed when running
# eval/run_eval.py locally (40 briefs would trip the recommend limit). Keep
# true in production.
_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"

limiter = Limiter(key_func=get_remote_address, default_limits=DEFAULT_LIMITS,
                  enabled=_ENABLED)

RATE_LIMIT_MESSAGE = (
    "Anh/Chị thao tác hơi nhanh — em xử lý không kịp. "
    "Vui lòng đợi một chút rồi thử lại nhé!"
)
