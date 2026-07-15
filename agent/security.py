"""Privacy helpers shared by logs, traces, and diagnostics."""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


REDACTED = "[REDACTED]"

_SENSITIVE_KEYS = {
    "api_key", "apikey", "authorization", "cookie", "email", "password",
    "phone", "cccd", "citizen_id", "address", "secret", "secret_key", "token", "access_token", "refresh_token",
}

_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9,10}(?!\d)"), "[REDACTED_PHONE]"),
    (re.compile(r"(?<!\d)\d{12}(?!\d)"), "[REDACTED_CCCD]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"\bvn--[A-Za-z0-9_-]{12,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"(?i)mongodb(?:\+srv)?://[^\s/@:]+:[^\s/@]+@"), "mongodb://[REDACTED]@"),
)


def redact_text(value: str) -> str:
    """Mask common PII and credential shapes while preserving useful context."""
    result = value
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_pii(value: Any, *, _depth: int = 0) -> Any:
    """Recursively return a redacted copy suitable for logs and external traces."""
    if _depth > 12:
        return "[TRUNCATED_DEPTH]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _SENSITIVE_KEYS or any(
                marker in normalized for marker in ("password", "secret", "api_key", "token")
            ):
                result[key] = REDACTED
            else:
                result[key] = redact_pii(item, _depth=_depth + 1)
        return result
    if isinstance(value, list):
        return [redact_pii(item, _depth=_depth + 1) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_pii(item, _depth=_depth + 1) for item in value)
    if isinstance(value, set):
        return {redact_pii(item, _depth=_depth + 1) for item in value}
    try:
        return deepcopy(value)
    except Exception:
        return str(value)


def redact_langfuse(data: Any = None, **_: Any) -> Any:
    """Adapt recursive redaction to Langfuse's ``mask(data=...)`` contract."""
    return redact_pii(data)
