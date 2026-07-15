"""
Drop-in entry point: same signature as handlers.freeform.handle_freeform.
Wired in router.py behind USE_LANGGRAPH_FREEFORM (default false).

Adds (Phase 1 steps 5–8):
- MongoDB checkpointer (thread_id = session_id) with graceful in-memory fallback
- Langfuse trace per request (nodes auto-traced via the langchain callback)
- Auto-mode: full-setup trigger phrases route to the planner→executor→critic
  subgraph; everything else goes through the chat graph.

⛔ Auto mode STOPS at a human-confirm proposal — order creation always goes
through the existing UI confirm → handle_setup phase 2 → order_guard +
idempotency. ADR 017: langgraph interrupt()/resume deferred until the frontend
grows a resume channel; the existing confirm gate provides the same guarantee.
"""
import uuid

from models import AgentResponse, ResponseMeta
from config import config
from graph.build import build_chat_graph, build_auto_graph
from agent_logger import alog
from request_context import get_request_id
from provider_resilience import PROVIDER_UNAVAILABLE_MESSAGE

_chat_graph = None
_auto_graph = None
_checkpointer = None

# Trigger phrases → auto mode (plan→execute→critique the whole campaign setup)
_AUTO_TRIGGERS = [
    "tự động tạo chiến dịch", "tự động setup", "tự setup toàn bộ",
    "làm hết giúp", "setup toàn bộ chiến dịch", "auto setup", "full auto",
    "tự động toàn bộ", "agent tự làm",
]


def _get_checkpointer():
    """MongoDBSaver on the existing camp_ads DB; None (stateless) if unavailable."""
    global _checkpointer
    if _checkpointer is None:
        try:
            from langgraph.checkpoint.mongodb import MongoDBSaver
            from pymongo import MongoClient
            client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            _checkpointer = MongoDBSaver(client, db_name=config.MONGODB_DB,
                                         checkpoint_collection_name="graph_checkpoints")
            print("✅ LangGraph checkpointer: MongoDB (graph_checkpoints)")
        except Exception as e:
            print(f"⚠ LangGraph checkpointer unavailable ({str(e)[:80]}) — running stateless")
            _checkpointer = False  # sentinel: tried and failed
    return _checkpointer or None


def _graphs():
    global _chat_graph, _auto_graph
    if _chat_graph is None:
        cp = _get_checkpointer()
        _chat_graph = build_chat_graph(checkpointer=cp)
        _auto_graph = build_auto_graph(checkpointer=cp)
    return _chat_graph, _auto_graph


def _langfuse_config(session_id: str, request_id: str, mode: str) -> dict:
    """Graph config incl. Langfuse callback when tracing is active."""
    cfg: dict = {"configurable": {"thread_id": session_id}}
    import os
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        try:
            from langfuse.langchain import CallbackHandler
            cfg["callbacks"] = [CallbackHandler()]
            cfg["metadata"] = {
                "langfuse_session_id": session_id,
                "langfuse_tags": [f"mode:{mode}"],
                "request_id": request_id,
            }
        except ImportError:
            pass
    return cfg


async def handle_freeform_graph(
    message: str,
    step: int,
    session_id: str,
    workspace: dict | None = None,
    workspace_revision: int | None = None,
    confirmed_steps: list[int] | None = None,
    workspace_events: list[str] | None = None,
) -> AgentResponse:
    msg_lower = message.lower().strip()
    mode = "auto" if any(t in msg_lower for t in _AUTO_TRIGGERS) else "chat"

    state = {
        "session_id": session_id,
        "request_id": (
            get_request_id() if get_request_id() != "-" else uuid.uuid4().hex[:12]
        ),
        "step": step,
        "user_message": message,
        "workspace": workspace or {},
        "workspace_revision": workspace_revision,
        "confirmed_steps": confirmed_steps or [],
        "workspace_events": workspace_events or [],
        "mode": mode,
        "current_task_idx": 0,
        "task_results": {},
        "retry_counts": {},
        "tokens_spent": 0,
        "token_budget": config.TOKEN_BUDGET_PER_REQUEST,
        # ⛔ RESET ALL TRANSIENT CHANNELS EVERY TURN. With a checkpointer,
        # any channel absent from the input keeps its checkpointed value from
        # the PREVIOUS turn — a stale response_text made the router short-
        # circuit to respond and replay the old answer verbatim (bug found in
        # prod logs 2026-07-04). Never remove these resets.
        "messages": [],
        "tool_rounds": 0,
        "plan": None,
        "critique": None,
        "pending_proposal": None,
        "response_text": "",
        "response_blocks": [],
        "response_meta": {},
        "workspace_update": None,
        "suggestions": [],
        "fallback_level": 0,
        "used_tool": "",
    }

    chat_graph, auto_graph = _graphs()
    graph = auto_graph if mode == "auto" else chat_graph
    # Separate checkpoint threads per graph — chat and auto share the state
    # schema, so sharing a thread would bleed channels between graphs.
    thread_id = f"{session_id}:auto" if mode == "auto" else session_id

    try:
        graph_config = _langfuse_config(session_id, state["request_id"], mode)
        graph_config["configurable"] = {"thread_id": thread_id}
        final = await graph.ainvoke(state, config=graph_config)
    except Exception as e:
        import traceback
        await alog(session_id, "error", {"handler": f"graph_{mode}", "error": str(e),
                                         "traceback": traceback.format_exc()[-600:]})
        return AgentResponse(
            text=PROVIDER_UNAVAILABLE_MESSAGE,
            blocks=[], meta=ResponseMeta(tool="freeform_chat", model="none", step=step),
        )

    return AgentResponse(
        text=final.get("response_text", ""),
        blocks=final.get("response_blocks", []),
        meta=ResponseMeta(
            tool=final.get("used_tool") or ("auto_mode" if mode == "auto" else "freeform_chat"),
            model=config.LLM_MODEL.split("/")[-1],
            step=step,
        ),
        workspace_update=final.get("workspace_update"),
        suggestions=final.get("suggestions", []),
    )
