"""Deterministic prompt-injection screen for untrusted text surfaces."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionFinding:
    rule: str


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = "".join(
        char for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )
    value = value.replace("đ", "d")
    value = re.sub(r"[\s._-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


_RULES = (
    ("instruction_override", re.compile(
        r"\b(ignore|disregard|forget|override)\b.{0,35}\b"
        r"(previous|prior|above|system|developer)\b.{0,25}\b"
        r"(instruction|instructions|rules|prompt|message)\b"
    )),
    ("instruction_override_vi", re.compile(
        r"\b(bo qua|quen|ghi de|vo hieu hoa)\b.{0,40}\b"
        r"(chi dan|huong dan|quy tac|lenh|prompt|thong diep)\b.{0,25}\b"
        r"(truoc|he thong|developer|ben tren)\b"
    )),
    ("role_spoof", re.compile(
        r"(^|[\n;])\s*(system|developer|assistant)\s*:|"
        r"\b(begin|new)\s+(system|developer)\s+(message|prompt)\b"
    )),
    ("secret_exfiltration", re.compile(
        r"\b(reveal|show|print|leak|exfiltrate|tiet lo|hien thi|in ra)\b.{0,40}\b"
        r"(system prompt|prompt he thong|api key|secret|token|environment|bien moi truong)\b"
    )),
    ("tool_forcing", re.compile(
        r"\b(call|invoke|execute|force|trigger|goi|thuc thi|bat buoc)\b.{0,35}\b"
        r"(update workspace|create order|order guard|commit workspace|delete session)\b"
    )),
    ("safety_override", re.compile(
        r"\b(return|mark|set|tra ve|dat)\b.{0,35}\b"
        r"(safety false|safety flag false|safe true|all flags false)\b"
    )),
    ("jailbreak", re.compile(
        r"\b(jailbreak|dan mode|do anything now|unrestricted mode|che do khong gioi han)\b"
    )),
    ("markup_injection", re.compile(r"<script\b|<system\b|\[system message\]|###\s*system\b")),
)


def detect_prompt_injection(text: str | None) -> InjectionFinding | None:
    normalized = _normalize(text or "")
    for name, pattern in _RULES:
        if pattern.search(normalized):
            return InjectionFinding(name)
    return None


def scan_untrusted_payload(value, path: str = "input") -> tuple[str, InjectionFinding] | None:
    if isinstance(value, str):
        finding = detect_prompt_injection(value)
        return (path, finding) if finding else None
    if isinstance(value, list):
        for index, item in enumerate(value):
            found = scan_untrusted_payload(item, f"{path}[{index}]")
            if found:
                return found
    if isinstance(value, dict):
        for key, item in value.items():
            found = scan_untrusted_payload(item, f"{path}.{key}")
            if found:
                return found
    return None
