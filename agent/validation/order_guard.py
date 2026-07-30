"""
Order Guard — deterministic server-side validation of every order payload
BEFORE it reaches POST /api/orders. Never trust LLM- or frontend-produced values.

Design: `validate_order_payload()` is a PURE function (all external data passed in)
so it is unit-testable with zero mocks. `guard_order()` is the thin async wrapper
that gathers live data (zone catalog, conflicts, DMP ids) and calls the pure core.

Phase-0 deliverable. The Phase-1 agentic path MUST route through guard_order()
too — no path from LLM output to order creation without this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlparse

# Budget ceilings (VND). Env-overridable via config; defaults here for pure-fn use.
DEFAULT_MAX_ORDER_BUDGET_VND = 5_000_000_000  # 5 tỷ
MAX_CAMPAIGN_DAYS = 370

ALLOWED_OBJECTIVES = {"awareness", "consideration", "conversion", "retention"}
DEFAULT_ALLOWED_CREATIVE_URL_HOSTS = (
    "api.pawgrammers.io.vn",
    "localhost",
    "127.0.0.1",
)


class OrderValidationError(Exception):
    """Raised when an order payload fails validation. `.reasons` lists all failures."""

    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))

    def as_user_message(self) -> str:
        """Vietnamese message safe to surface in a chat `info` block."""
        bullet = "\n".join(f"- {r}" for r in self.reasons)
        return f"⚠ Không thể tạo chiến dịch — payload không hợp lệ:\n{bullet}"


@dataclass
class GuardContext:
    """Everything the pure validator needs from the outside world."""

    brief: dict                      # session.form_state.brief (source of truth)
    known_zone_ids: set[str]         # from zone_catalog.get_zone_map()
    known_dmp_ids: set[str]          # from audience_library segment _ids
    conflict_map: dict = field(default_factory=dict)  # from order_api.fetch_zone_conflicts
    creative_verdicts: dict = field(default_factory=dict)
    require_creative_verdict: bool = False
    max_budget_vnd: int = DEFAULT_MAX_ORDER_BUDGET_VND
    today: date | None = None        # injectable for tests
    allowed_creative_url_hosts: tuple[str, ...] = DEFAULT_ALLOWED_CREATIVE_URL_HOSTS


def _parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat((s or "")[:10])
    except (ValueError, TypeError):
        return None


def validate_order_payload(payload: dict, ctx: GuardContext) -> list[str]:
    """
    Returns list of human-readable failure reasons (empty = valid).
    Collects ALL failures instead of stopping at the first — better error UX
    and better test assertions.
    """
    reasons: list[str] = []
    today = ctx.today or date.today()

    # ── 1. Budget bounds ────────────────────────────────────────────────────
    budget = payload.get("budget")
    if not isinstance(budget, (int, float)) or isinstance(budget, bool):
        reasons.append(f"Budget không phải là số: {budget!r}")
    elif budget != budget or budget <= 0:  # NaN check: NaN != NaN
        reasons.append(f"Budget phải > 0 (nhận được {budget!r})")
    elif budget > ctx.max_budget_vnd:
        reasons.append(
            f"Budget {budget:,.0f} VND vượt trần {ctx.max_budget_vnd:,.0f} VND"
        )

    # ── 2. Budget consistency vs confirmed brief (LLM may not invent numbers) ─
    brief_budget_m = ctx.brief.get("budget", 0)
    if isinstance(budget, (int, float)) and isinstance(brief_budget_m, (int, float)):
        expected_vnd = brief_budget_m * 1_000_000
        if expected_vnd > 0 and budget != expected_vnd:
            reasons.append(
                f"Budget không khớp brief đã xác nhận: payload {budget:,.0f} VND "
                f"≠ brief {expected_vnd:,.0f} VND"
            )

    # ── 3. Zone existence ───────────────────────────────────────────────────
    placements = payload.get("placements") or []
    if not placements:
        reasons.append("Chưa chọn zone nào (placements rỗng)")
    unknown_zones = [z for z in placements if z not in ctx.known_zone_ids]
    if unknown_zones:
        reasons.append(f"Zone không tồn tại trong catalog: {', '.join(map(str, unknown_zones))}")

    # ── 4. Zone booking conflicts (re-checked at creation time — TOCTOU guard) ─
    request_key = payload.get("idempotencyKey") or ""
    conflicted = [
        z for z in placements
        if ctx.conflict_map.get(z)
        and not (
            request_key
            and ctx.conflict_map[z].get("idempotencyKey") == request_key
        )
    ]
    if conflicted:
        details = ", ".join(
            f"{z} (đã đặt bởi {ctx.conflict_map[z].get('orderId', '?')})" for z in conflicted
        )
        reasons.append(f"Zone đã bị đặt trong khoảng thời gian này: {details}")

    # ── 5. Dates ────────────────────────────────────────────────────────────
    start = _parse_date(payload.get("startDate", ""))
    end = _parse_date(payload.get("endDate", ""))
    if not start or not end:
        reasons.append("startDate/endDate thiếu hoặc sai định dạng (cần YYYY-MM-DD)")
    else:
        if start > end:
            reasons.append(f"startDate {start} sau endDate {end}")
        if end < today:
            reasons.append(f"endDate {end} đã ở quá khứ")
        if (end - start).days > MAX_CAMPAIGN_DAYS:
            reasons.append(f"Chiến dịch dài {(end - start).days} ngày — vượt trần {MAX_CAMPAIGN_DAYS} ngày")

    # ── 6. Objective whitelist ──────────────────────────────────────────────
    if payload.get("objective") not in ALLOWED_OBJECTIVES:
        reasons.append(f"Objective không hợp lệ: {payload.get('objective')!r}")

    # ── 7. DMP segment ids exist ────────────────────────────────────────────
    dmp_include = (payload.get("dmp") or {}).get("include") or []
    if ctx.known_dmp_ids:  # skip check only if catalog unavailable (logged by caller)
        unknown_dmp = [d for d in dmp_include if d not in ctx.known_dmp_ids]
        if unknown_dmp:
            reasons.append(f"DMP segment không tồn tại: {', '.join(map(str, unknown_dmp[:5]))}")

    # ── 8. Creatives: zones ⊆ placements; URLs on our host ─────────────────
    placement_set = set(placements)
    creative_zone_set: set[str] = set()
    for c in payload.get("creatives") or []:
        creative_zone_set.update(c.get("zones") or [])
        stray = [z for z in (c.get("zones") or []) if z not in placement_set]
        if stray:
            reasons.append(
                f"Creative '{c.get('name', '?')}' gán vào zone ngoài placements: {', '.join(stray)}"
            )
        url = c.get("url") or ""
        if url and not url.startswith("data:"):
            try:
                creative_host = (urlparse(url).hostname or "").lower()
            except Exception:
                creative_host = ""
            host_ok = creative_host in {
                host.lower() for host in ctx.allowed_creative_url_hosts
            }
            if not host_ok:
                reasons.append(f"Creative URL không thuộc host cho phép: {url[:80]}")

        if ctx.require_creative_verdict:
            analysis_id = c.get("analysisId") or ""
            verdict = ctx.creative_verdicts.get(analysis_id)
            if not analysis_id:
                reasons.append(f"Creative '{c.get('name', '?')}' thiếu analysisId")
            elif not verdict:
                reasons.append(
                    f"Creative '{c.get('name', '?')}' không có verdict server-side hợp lệ"
                )
            elif verdict.get("url") != url:
                reasons.append(
                    f"Creative '{c.get('name', '?')}' không khớp URL đã được phân tích"
                )
            elif verdict.get("effective_status") not in {"auto_approved", "approved_override"}:
                review = "; ".join(verdict.get("review_reasons") or [])
                reasons.append(
                    f"Creative '{c.get('name', '?')}' chưa được duyệt: "
                    f"{review or verdict.get('status', 'unknown')}"
                )

    uncovered = placement_set - creative_zone_set
    if uncovered:
        reasons.append(
            "Các zone chưa được gán creative: " + ", ".join(sorted(uncovered))
        )

    return reasons


async def guard_order(payload: dict, session: dict) -> None:
    """
    Async wrapper: gathers live context and raises OrderValidationError on failure.
    Call this in handlers/setup.py::_order_create and in any agentic order path.
    """
    import asyncio

    from config import config
    from tools.zone_catalog import get_zone_map
    from tools.order_api import fetch_zone_conflicts
    from tools.audience_library import get_all_segments

    brief = session.get("form_state", {}).get("brief", {}) or {}

    zone_map, conflict_map, segments = await asyncio.gather(
        get_zone_map(),
        fetch_zone_conflicts(payload.get("startDate", ""), payload.get("endDate", "")),
        get_all_segments(),
        return_exceptions=True,
    )
    # Fail-closed on zone catalog (core check); fail-open with log on the rest.
    if isinstance(zone_map, Exception):
        raise OrderValidationError([f"Không lấy được zone catalog để kiểm tra: {zone_map}"])
    known_dmp_ids: set[str] = set()
    if not isinstance(segments, Exception):
        known_dmp_ids = {s.get("_id", "") for s in segments if s.get("_id")}
    creative_verdicts: dict = {}
    if config.USE_VLM_CREATIVE:
        from creative_intel.service import get_intel_by_ids

        analysis_ids = [
            c.get("analysisId", "") for c in (payload.get("creatives") or [])
            if c.get("analysisId")
        ]
        creative_verdicts = await get_intel_by_ids(session.get("_id", "default"), analysis_ids)
    ctx = GuardContext(
        brief=brief,
        known_zone_ids=set(zone_map.keys()),
        known_dmp_ids=known_dmp_ids,
        conflict_map=conflict_map if not isinstance(conflict_map, Exception) else {},
        creative_verdicts=creative_verdicts,
        require_creative_verdict=config.USE_VLM_CREATIVE,
        max_budget_vnd=getattr(config, "MAX_ORDER_BUDGET_VND", DEFAULT_MAX_ORDER_BUDGET_VND),
        allowed_creative_url_hosts=config.ALLOWED_CREATIVE_URL_HOSTS,
    )

    reasons = validate_order_payload(payload, ctx)
    if reasons:
        raise OrderValidationError(reasons)
