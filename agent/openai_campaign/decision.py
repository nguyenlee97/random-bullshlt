"""GPT-5.4-mini semantic FAQ/action planning without keyword routing."""
from __future__ import annotations

import json

from config import config
from openai_campaign.client import get_client, safety_identifier
from openai_campaign.prompts import TURN_DECISION_INSTRUCTIONS
from openai_campaign.schemas import TurnDecision


def _bounded_history(history: list[dict]) -> list[dict]:
    return [
        {
            "role": "assistant" if item.get("role") == "assistant" else "user",
            "content": str(item.get("content") or "")[-2000:],
        }
        for item in history[-12:]
        if item.get("content")
    ]


def _workspace_summary(workspace: dict | None) -> dict:
    value = workspace or {}
    artifacts = value.get("artifacts") or {}

    def artifact(name: str, fallback=None):
        raw = artifacts.get(name, {}).get("value")
        if raw is None:
            raw = value.get(name, fallback)
        return fallback if raw is None else raw

    brief = artifact("brief", {}) if isinstance(artifact("brief", {}), dict) else {}
    audience = artifact("audience", artifact("segment", {}))
    audience = audience if isinstance(audience, dict) else {}
    creative = artifact("creative", {})
    creative = creative if isinstance(creative, dict) else {}
    placements = artifact("placements", artifact("setup", {}))
    placements = placements if isinstance(placements, dict) else {}
    return {
        "revision": value.get("revision"),
        "experience_mode": value.get("experience_mode"),
        "brief": {
            key: brief.get(key)
            for key in (
                "brand", "objective", "kpi", "budget", "startDate", "endDate"
            )
            if brief.get(key) not in (None, "")
        },
        "audience_ids": [
            str(item.get("_id") or item.get("segmentId") or "")
            for item in (audience.get("attrs") or [])[:30]
            if item.get("_id") or item.get("segmentId")
        ],
        "creative_names": [
            str(item.get("name") or item.get("id") or "")
            for item in (creative.get("files") or [])[:20]
            if item.get("name") or item.get("id")
        ],
        "selected_zone_ids": [
            str(item) for item in (placements.get("selectedZoneIds") or [])[:30]
        ],
    }


async def decide_turn(
    *,
    session_id: str,
    message: str,
    history: list[dict],
    step: int,
    workspace: dict | None,
    pending_proposal: dict | None,
    allowed_capabilities: list[str],
    client=None,
) -> TurnDecision:
    """Return semantic intent evidence using the run's locked OpenAI model."""
    payload = {
        "latest_message": message,
        "recent_messages": _bounded_history(history),
        "current_step": step,
        "workspace": _workspace_summary(workspace),
        "pending_proposal": {
            "proposal_id": (pending_proposal or {}).get("proposal_id"),
            "field": (pending_proposal or {}).get("field"),
            "reason": (pending_proposal or {}).get("reason"),
        } if pending_proposal else None,
        "allowed_capabilities": allowed_capabilities,
    }
    api = client or get_client()
    response = await api.responses.parse(
        model=config.OPENAI_CAMPAIGN_MODEL,
        instructions=TURN_DECISION_INSTRUCTIONS,
        input=json.dumps(payload, ensure_ascii=False),
        text_format=TurnDecision,
        reasoning={"effort": config.OPENAI_CAMPAIGN_REASONING_EFFORT},
        max_output_tokens=min(config.OPENAI_CAMPAIGN_MAX_OUTPUT_TOKENS, 1000),
        store=False,
        safety_identifier=safety_identifier(session_id),
    )
    if response.output_parsed is None:
        raise RuntimeError("OpenAI returned no semantic turn decision")
    return response.output_parsed
