"""Export candidate user-facing Python literals for wording review."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "copy-review" / "06-raw-agent-literals.md"

FILES = [
    *(ROOT / "agent" / "handlers").glob("*.py"),
    ROOT / "agent" / "router.py",
    ROOT / "agent" / "campaign_models.py",
    ROOT / "agent" / "zalo_campaign_agent.py",
    ROOT / "agent" / "zalo_openai.py",
]

VIETNAMESE = re.compile(r"[À-ỹĐđ]")
SENTENCE = re.compile(r"[A-Za-zÀ-ỹ].*\s+.*[A-Za-zÀ-ỹ]")
CODE_ONLY = re.compile(r"^[A-Za-z0-9_./:{}-]+$")


def normalize(value: str) -> str:
    return " ".join(value.split())


def render_joined(node: ast.JoinedStr) -> str:
    parts: list[str] = []
    expression_index = 0
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        elif isinstance(value, ast.FormattedValue):
            expression_index += 1
            parts.append(f"{{expression_{expression_index}}}")
    return normalize("".join(parts))


def looks_user_facing(value: str) -> bool:
    if len(value) < 2:
        return False
    if value.startswith(("http://", "https://", "/", "mongodb://")):
        return False
    if CODE_ONLY.fullmatch(value):
        return False
    if re.fullmatch(r"[\d.,:;/×%+\-–—()\s]+", value):
        return False
    return bool(VIETNAMESE.search(value) or SENTENCE.search(value))


def is_docstring_node(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    if not isinstance(parent, ast.Expr):
        return False
    owner = parents.get(parent)
    if not isinstance(owner, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False
    return bool(owner.body and owner.body[0] is parent)


sections: list[str] = []
total = 0

for file_path in sorted(set(FILES)):
    if not file_path.exists():
        continue
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    entries: list[tuple[int, str, str]] = []
    seen: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if is_docstring_node(node, parents):
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = normalize(node.value)
            kind = "string"
        elif isinstance(node, ast.JoinedStr):
            value = render_joined(node)
            kind = "template"
        else:
            continue
        key = (getattr(node, "lineno", 1), value)
        if key in seen or not looks_user_facing(value):
            continue
        seen.add(key)
        entries.append((key[0], kind, value))

    entries.sort(key=lambda entry: (entry[0], entry[2].casefold()))
    if not entries:
        continue
    total += len(entries)
    relative = file_path.relative_to(ROOT).as_posix()
    sections.extend(
        [
            f"## `{relative}`",
            "",
            "| Line | Kind | Literal copy |",
            "| ---: | --- | --- |",
        ]
    )
    for line, kind, value in entries:
        escaped = value.replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`")
        sections.append(f"| {line} | {kind} | {escaped} |")
    sections.append("")

output = "\n".join(
    [
        "# Raw agent source-literal inventory",
        "",
        "This file is generated from Python source and is a completeness appendix",
        "for wording review. It includes deterministic user-facing messages, Zalo",
        "responses, and some prompt or internal literals that a mechanical extractor",
        "cannot safely classify. It is not a proposed rewrite.",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Candidate literals: {total}",
        "",
        *sections,
    ]
)

OUTPUT.write_text(output, encoding="utf-8")
print(f"Wrote {total} candidate literals to {OUTPUT.relative_to(ROOT)}")
