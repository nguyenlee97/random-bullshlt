"""Conservative policy checks over OCR text returned by the creative VLM."""
from __future__ import annotations

import re
import unicodedata


def _text(lines: list[str] | str | None) -> str:
    if isinstance(lines, str):
        lines = [lines]
    value = " ".join(str(line) for line in (lines or []))
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", value)


_SAFETY_TERMS = {
    "alcohol": (
        "whisky", "whiskey", "craft beer", "beer tasting", "drink responsibly",
        "rượu", "bia thủ công",
    ),
    "gambling": (
        "casino", "bet now", "jackpot", "sportsbook", "đặt cược", "cá cược",
    ),
    "political": (
        "vote 20", "candidate ", "bầu cử", "vận động bầu cử", "election campaign",
    ),
    "medical": (
        "miracle cure", "prescription", "diabetes cure", "guaranteed results in",
        "ask a doctor", "medical treatment", "thuốc kê đơn", "điều trị",
    ),
    "nsfw": (
        "adult content", "adult only", "18+", "nội dung người lớn",
    ),
}

_INJECTION_TERMS = (
    "ignore all rules",
    "ignore rules",
    "ignore previous",
    "return safety=false",
    "mark every safety flag false",
    "system:",
    "developer:",
)


def detect_safety_flags(lines: list[str] | str | None) -> set[str]:
    value = _text(lines)
    return {
        flag for flag, terms in _SAFETY_TERMS.items()
        if any(term in value for term in terms)
    }


def contains_prompt_injection(lines: list[str] | str | None) -> bool:
    value = _text(lines)
    return any(term in value for term in _INJECTION_TERMS)
