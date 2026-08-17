"""Dispatch one immutable conversation to exactly one campaign engine."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from campaign_models import GREENNODE_MINIMAX, OPENAI_GPT_5_4_MINI, normalize_conversation_model


class CampaignEngineUnavailable(RuntimeError):
    pass


async def dispatch_freeform(
    conversation_model: str,
    *,
    greennode_handler: Callable[..., Awaitable[Any]],
    openai_handler: Callable[..., Awaitable[Any]] | None = None,
    **kwargs,
):
    """Invoke the locked engine without fallback to the other component."""
    selected = normalize_conversation_model(conversation_model)
    if selected == GREENNODE_MINIMAX:
        return await greennode_handler(**kwargs)
    if selected == OPENAI_GPT_5_4_MINI:
        if openai_handler is None:
            from openai_campaign.engine import handle_openai_freeform
            openai_handler = handle_openai_freeform
        return await openai_handler(**kwargs)
    raise CampaignEngineUnavailable(f"unsupported campaign engine: {selected}")


async def dispatch_guided(
    conversation_model: str,
    *,
    greennode_handler: Callable[..., Awaitable[Any]],
    openai_handler: Callable[..., Awaitable[Any]],
    **kwargs,
):
    """Dispatch one Guided model operation without provider fallback.

    Deterministic Guided handlers do not need this boundary. It is reserved for
    operations that perform model inference, so an OpenAI-locked conversation
    can never enter a legacy GreenNode generator by bypassing free-form routing.
    """
    selected = normalize_conversation_model(conversation_model)
    if selected == GREENNODE_MINIMAX:
        return await greennode_handler(**kwargs)
    if selected == OPENAI_GPT_5_4_MINI:
        return await openai_handler(**kwargs)
    raise CampaignEngineUnavailable(f"unsupported campaign engine: {selected}")


async def dispatch_autopilot(
    conversation_model: str,
    *,
    greennode_handler: Callable[..., Awaitable[Any]],
    openai_handler: Callable[..., Awaitable[Any]],
    **kwargs,
):
    """Dispatch one Autopilot inference from the persisted run model.

    The worker passes the durable run model into this boundary on every
    attempt. Provider errors propagate to the worker retry policy and never
    cause a call to the sibling provider.
    """
    selected = normalize_conversation_model(conversation_model)
    if selected == GREENNODE_MINIMAX:
        return await greennode_handler(**kwargs)
    if selected == OPENAI_GPT_5_4_MINI:
        return await openai_handler(**kwargs)
    raise CampaignEngineUnavailable(f"unsupported campaign engine: {selected}")
