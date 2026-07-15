"""Fail when committed source contains credentials with known token shapes."""

from __future__ import annotations

import re
import shutil
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_FILE_BYTES = 2_000_000
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2"}
PATTERNS = {
    "OpenAI API key": re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b"),
    "Langfuse secret key": re.compile(r"\bsk-lf-[A-Za-z0-9-]{20,}\b"),
    "MaaS API key": re.compile(r"\bvn--[A-Za-z0-9_-]{20,}\b"),
    "MongoDB URI with password": re.compile(
        r"mongodb(?:\+srv)?://[^\s:/@<>{}$]+:[^\s/@<>{}$]+@", re.IGNORECASE
    ),
    "Bearer token": re.compile(r"\bBearer\s+[A-Za-z0-9._-]{24,}\b", re.IGNORECASE),
}


def tracked_files() -> list[Path]:
    git = shutil.which("git")
    if git is None:
        windows_git = Path(r"C:\Program Files\Git\cmd\git.exe")
        git = str(windows_git) if windows_git.exists() else "git"
    result = subprocess.run(
        [git, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, check=True, capture_output=True
    )
    return [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def scan_history() -> list[tuple[str, str, int]]:
    git = shutil.which("git") or str(Path(r"C:\Program Files\Git\cmd\git.exe"))
    commits = subprocess.run(
        [git, "rev-list", "--all"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    findings: list[tuple[str, str, int]] = []
    needles = ("sk-proj-", "sk-lf-", "vn--", "mongodb://", "mongodb+srv://", "Bearer ")
    for commit in commits:
        result = subprocess.run(
            [git, "grep", "-n", "-I", *sum((["-e", item] for item in needles), []), commit, "--"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        for line in result.stdout.splitlines():
            match = re.match(r"[^:]+:(.*?):(\d+):(.*)", line)
            if match and any(pattern.search(match.group(3)) for pattern in PATTERNS.values()):
                findings.append((commit[:12], match.group(1), int(match.group(2))))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    findings: list[tuple[str, str, int]] = []
    for path in tracked_files():
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((label, str(path.relative_to(ROOT)), line_number))

    if findings:
        print("Potential committed credentials detected (values intentionally hidden):")
        for label, path, line in findings:
            print(f"- {label}: {path}:{line}")
        return 1
    print("Tracked-secret scan: PASS")
    if args.history:
        historical = scan_history()
        if historical:
            print("Potential credential shapes exist in Git history (values hidden):")
            for commit, path, line in historical[:100]:
                print(f"- commit {commit}: {path}:{line}")
            if len(historical) > 100:
                print(f"- ... {len(historical) - 100} more findings")
            return 1
        print("Git-history secret scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
