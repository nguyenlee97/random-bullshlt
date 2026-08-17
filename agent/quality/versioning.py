"""Reproducible version manifest for quality records and eval exports."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import os
from pathlib import Path

from config import config
from version import BUILD_VERSION


AGENT_ROOT = Path(__file__).resolve().parents[1]
QUALITY_SCHEMA_VERSION = "quality-v1"

PROMPT_INPUTS = (
    AGENT_ROOT / "prompts",
    AGENT_ROOT / "openai_campaign" / "prompts.py",
    AGENT_ROOT / "zalo_openai.py",
)
TOOL_INPUTS = (
    AGENT_ROOT / "tools" / "registry.py",
    AGENT_ROOT / "openai_campaign" / "tools.py",
    AGENT_ROOT / "zalo_tools.py",
)
GUARD_INPUTS = (
    AGENT_ROOT / "guardrails",
    AGENT_ROOT / "prompt_guard.py",
)


def _iter_files(paths: tuple[Path, ...]):
    for path in paths:
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from sorted(
                item for item in path.rglob("*")
                if item.is_file() and "__pycache__" not in item.parts
            )


def _content_hash(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    found = False
    for path in _iter_files(paths):
        found = True
        digest.update(str(path.relative_to(AGENT_ROOT)).replace("\\", "/").encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()[:12]}" if found else "unknown"


@lru_cache(maxsize=1)
def _base_manifest() -> dict:
    return {
        "agent_build_version": BUILD_VERSION,
        "git_sha": os.getenv("GIT_SHA") or None,
        "campaign_engine": None,
        "model_provider": None,
        "model_name": None,
        "prompt_version": _content_hash(PROMPT_INPUTS),
        "tool_contract_version": _content_hash(TOOL_INPUTS),
        "guard_policy_version": (
            f"{config.GUARDRAIL_POLICY_VERSION}+"
            f"{_content_hash(GUARD_INPUTS).split(':')[-1]}"
        ),
        "rag_index_version": os.getenv("RAG_INDEX_VERSION") or None,
        "creative_policy_version": os.getenv("CREATIVE_POLICY_VERSION") or None,
        "approval_policy": None,
        "quality_schema_version": QUALITY_SCHEMA_VERSION,
    }


def get_version_manifest(
    *,
    model: str | None = None,
    engine: str | None = None,
    approval_policy: str | None = None,
) -> dict:
    manifest = deepcopy(_base_manifest())
    model_name = model if model and model != "none" else None
    manifest["campaign_engine"] = engine
    manifest["model_name"] = model_name
    if model_name:
        lowered = model_name.lower()
        manifest["model_provider"] = (
            "openai" if lowered.startswith(("gpt-", "o1", "o3", "o4"))
            else "greennode"
        )
    elif engine == "openai":
        manifest["model_provider"] = "openai"
        manifest["model_name"] = config.OPENAI_CAMPAIGN_MODEL
    elif engine == "greennode":
        manifest["model_provider"] = "greennode"
        manifest["model_name"] = config.LLM_MODEL
    manifest["approval_policy"] = approval_policy
    return manifest
