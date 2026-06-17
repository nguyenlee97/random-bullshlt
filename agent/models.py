"""
Pydantic models — request/response contracts for POST /api/agent/chat.
Matches agentApi.js frontend payload exactly.
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel


# ── Inbound: form data sub-models ────────────────────────────────────────────

class BriefData(BaseModel):
    brand: str = ""
    advertiser: str = ""
    objective: str = "awareness"   # awareness | consideration | conversion | retention
    kpi: str = ""
    budget: float = 0              # in triệu VND (millions)
    startDate: str = ""
    endDate: str = ""
    notes: str = ""


class CreativeFile(BaseModel):
    name: str = ""
    type: str = ""                 # MIME type e.g. "image/png"
    size: int = 0                  # bytes
    width: int = 0
    height: int = 0
    url: str = ""                  # VPS upload URL from POST /api/creative/upload


class CreativeData(BaseModel):
    files: list[CreativeFile] = []


class SegmentAttr(BaseModel):
    _id: str = ""                  # MongoDB ObjectId — used in dmp.include[]
    segmentId: str = ""
    type: str = ""
    category: str = ""
    name: str = ""
    fullLabel: str = ""
    sizeMin: int | None = None
    sizeMax: int | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class SegmentData(BaseModel):
    attrs: list[dict] = []         # Raw DMP attribute objects (keep _id)
    size: int = 0                  # Calculated audience size


class SetupData(BaseModel):
    phase: int = 0                 # 0=zone recommend, 1=creative match, 2=order create
    selectedZoneIds: list[str] = []
    assignments: dict[str, int] = {}   # { zoneId: fileIndex }
    targeting: dict[str, list] = {}    # Advanced targeting (optional)
    regenerate: bool = False
    fileUrls: dict[str, str] = {}      # { str(fileIndex): uploadedUrl } — from frontend upload


class FormData(BaseModel):
    brief: BriefData | None = None
    creative: CreativeData | None = None
    segment: SegmentData | None = None
    setup: SetupData | None = None


# ── Inbound: main chat request ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str = "default"
    step: int = -1                 # -1=boot, 0=brief, 1=audience, 2=creative, 3=setup, 4=result
    message: str = ""              # Free-form text
    formData: FormData | None = None
    workspace: dict | None = None          # Live formState from frontend (compact, no dataUrls)
    confirmed_steps: list[int] | None = None   # Step indices that are "done" (locked)
    workspace_events: list[str] | None = None  # Human-readable descriptions of direct UI changes


# ── Outbound: agent response ──────────────────────────────────────────────────

class ResponseMeta(BaseModel):
    tool: str | None = None        # Which tool/handler ran
    model: str = "none"            # "minimax" | "none"
    step: int = -1


class Block(BaseModel):
    """
    Rich UI block. Types:
    - table:              { title, columns[], rows[][] }
    - info:               { text }
    - campaign_list:      { campaigns[] }
    - audience_size:      { size, breakdown[] }
    - metric_grid:        { metrics[] }
    - workspace_proposal: { changes: {field, value, reason}, is_locked, warning }
    """
    type: str
    model_config = {"extra": "allow"}


class AgentResponse(BaseModel):
    text: str = ""
    blocks: list[dict] = []
    meta: ResponseMeta | dict = {}
    workspace_update: dict | None = None   # Patch to apply to formState after user confirms
    suggestions: list = []           # Quick-reply chips — strings or {label, action, text}
