"""Deterministic date normalization for campaign Brief inputs."""
from __future__ import annotations

from datetime import date, datetime
import re
import unicodedata
from typing import Any


_DAY_FIRST_RE = re.compile(
    r"^(?:ngay\s+)?(?P<day>\d{1,2})\s*"
    r"(?:[/.\-]\s*|\s+thang\s+)(?P<month>\d{1,2})\s*"
    r"(?:[/.\-]\s*|\s+nam\s+)(?P<year>\d{4})$",
    re.IGNORECASE,
)
_YEAR_FIRST_RE = re.compile(
    r"^(?P<year>\d{4})\s*[/.\-]\s*"
    r"(?P<month>\d{1,2})\s*[/.\-]\s*(?P<day>\d{1,2})$",
)
_ENGLISH_DATE_FORMATS = (
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
)


def _ascii_words(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _validated_iso(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def normalize_brief_date(value: Any) -> Any:
    """Return an ISO date for common unambiguous campaign date formats.

    Natural-language interpretation remains model-owned. This boundary repairs
    the structured value when a provider preserves the user's Vietnamese
    day-first formatting instead of returning the canonical ``YYYY-MM-DD``
    contract.
    """
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        return value

    original = value.strip()
    if not original:
        return original

    # Accept an exact ISO date or a fully valid ISO datetime without changing
    # the calendar day. Never trust an ISO-looking prefix followed by garbage.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", original):
        try:
            return date.fromisoformat(original).isoformat()
        except ValueError:
            return original
    try:
        return datetime.fromisoformat(
            original[:-1] + "+00:00" if original.endswith("Z") else original
        ).date().isoformat()
    except ValueError:
        pass

    normalized_words = re.sub(
        r"\s+",
        " ",
        _ascii_words(original).replace(",", " ").strip(),
    )
    for pattern in (_DAY_FIRST_RE, _YEAR_FIRST_RE):
        match = pattern.fullmatch(normalized_words)
        if match:
            converted = _validated_iso(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            )
            return converted if converted is not None else original

    for date_format in _ENGLISH_DATE_FORMATS:
        try:
            return datetime.strptime(normalized_words, date_format).date().isoformat()
        except ValueError:
            continue

    # Preserve unknown values so the existing domain validator can reject them
    # with its normal actionable error instead of silently guessing.
    return original
