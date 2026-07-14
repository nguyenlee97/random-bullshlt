"""Unit tests for validation/order_guard.py — pure core, zero mocks needed."""
from datetime import date

import pytest

from validation.order_guard import (
    GuardContext,
    OrderValidationError,
    validate_order_payload,
)

TODAY = date(2026, 7, 4)
ZONES = {"ZN-001", "ZN-002", "ZN-003"}
DMP = {"64aa01", "64aa02"}


def make_payload(**over) -> dict:
    p = {
        "brand": "ZUMA Ice",
        "objective": "awareness",
        "budget": 600_000_000,
        "startDate": "2026-07-10",
        "endDate": "2026-08-10",
        "placements": ["ZN-001", "ZN-002"],
        "dmp": {"include": ["64aa01"], "exclude": []},
        "creatives": [
            {"name": "banner.png", "zones": ["ZN-001", "ZN-002"], "url": "https://api.pawgrammers.io.vn/up/banner.png"}
        ],
    }
    p.update(over)
    return p


def make_ctx(**over) -> GuardContext:
    kw = dict(
        brief={"budget": 600},  # triệu → 600M VND
        known_zone_ids=ZONES,
        known_dmp_ids=DMP,
        conflict_map={},
        today=TODAY,
    )
    kw.update(over)
    return GuardContext(**kw)


def test_valid_payload_passes():
    assert validate_order_payload(make_payload(), make_ctx()) == []


# ── budget ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", [0, -5, float("nan"), "600", None, True])
def test_budget_bounds(bad):
    reasons = validate_order_payload(make_payload(budget=bad), make_ctx())
    assert any("Budget" in r for r in reasons)


def test_budget_over_ceiling():
    reasons = validate_order_payload(
        make_payload(budget=999_000_000_000), make_ctx(brief={"budget": 999_000})
    )
    assert any("vượt trần" in r for r in reasons)


def test_llm_invented_budget_rejected():
    # brief says 600M but payload says 900M — LLM hallucination case
    reasons = validate_order_payload(make_payload(budget=900_000_000), make_ctx())
    assert any("không khớp brief" in r for r in reasons)


# ── zones ─────────────────────────────────────────────────────────────────────
def test_unknown_zone_rejected():
    reasons = validate_order_payload(make_payload(placements=["ZN-001", "ZN-999"]), make_ctx())
    assert any("ZN-999" in r for r in reasons)


def test_empty_placements_rejected():
    reasons = validate_order_payload(make_payload(placements=[], creatives=[]), make_ctx())
    assert any("placements rỗng" in r for r in reasons)


def test_conflict_recheck_blocks():
    ctx = make_ctx(conflict_map={"ZN-002": {"orderId": "ORD-2026-004"}})
    reasons = validate_order_payload(make_payload(), ctx)
    assert any("ORD-2026-004" in r for r in reasons)


# ── dates ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "start,end,frag",
    [
        ("2026-08-10", "2026-07-10", "sau endDate"),
        ("2026-01-01", "2026-02-01", "quá khứ"),
        ("2026-07-10", "2027-12-31", "vượt trần"),
        ("", "2026-08-10", "thiếu hoặc sai"),
        ("not-a-date", "2026-08-10", "thiếu hoặc sai"),
    ],
)
def test_date_rules(start, end, frag):
    reasons = validate_order_payload(make_payload(startDate=start, endDate=end), make_ctx())
    assert any(frag in r for r in reasons), reasons


# ── objective / dmp / creatives ──────────────────────────────────────────────
def test_bad_objective():
    reasons = validate_order_payload(make_payload(objective="virality"), make_ctx())
    assert any("Objective" in r for r in reasons)


def test_unknown_dmp_id():
    reasons = validate_order_payload(
        make_payload(dmp={"include": ["ffff99"], "exclude": []}), make_ctx()
    )
    assert any("DMP" in r for r in reasons)


def test_dmp_check_skipped_when_catalog_down():
    # fail-open: empty known_dmp_ids means catalog unavailable
    reasons = validate_order_payload(
        make_payload(dmp={"include": ["ffff99"], "exclude": []}),
        make_ctx(known_dmp_ids=set()),
    )
    assert not any("DMP" in r for r in reasons)


def test_creative_zone_outside_placements():
    reasons = validate_order_payload(
        make_payload(creatives=[{"name": "b.png", "zones": ["ZN-003"], "url": ""}]),
        make_ctx(),
    )
    assert any("ngoài placements" in r for r in reasons)


def test_creative_foreign_url_rejected():
    reasons = validate_order_payload(
        make_payload(creatives=[{"name": "b.png", "zones": ["ZN-001"], "url": "https://evil.example/x.png"}]),
        make_ctx(),
    )
    assert any("host cho phép" in r for r in reasons)


def test_every_placement_requires_a_creative():
    reasons = validate_order_payload(
        make_payload(creatives=[{
            "name": "b.png", "zones": ["ZN-001"],
            "url": "https://api.pawgrammers.io.vn/up/b.png",
        }]),
        make_ctx(),
    )
    assert any("ZN-002" in r and "chưa được gán" in r for r in reasons)


def test_server_side_creative_verdict_is_required_when_enabled():
    creative = {
        "name": "b.png",
        "zones": ["ZN-001", "ZN-002"],
        "url": "https://api.pawgrammers.io.vn/up/b.png",
        "analysisId": "ci-1",
    }
    blocked = validate_order_payload(
        make_payload(creatives=[creative]),
        make_ctx(require_creative_verdict=True, creative_verdicts={
            "ci-1": {"url": creative["url"], "status": "needs_review", "effective_status": "needs_review",
                     "review_reasons": ["low confidence"]},
        }),
    )
    assert any("chưa được duyệt" in reason for reason in blocked)

    passed = validate_order_payload(
        make_payload(creatives=[creative]),
        make_ctx(require_creative_verdict=True, creative_verdicts={
            "ci-1": {"url": creative["url"], "status": "needs_review", "effective_status": "approved_override"},
        }),
    )
    assert passed == []

    substituted = validate_order_payload(
        make_payload(creatives=[creative]),
        make_ctx(require_creative_verdict=True, creative_verdicts={
            "ci-1": {"url": "https://api.pawgrammers.io.vn/up/other.png",
                     "status": "auto_approved", "effective_status": "auto_approved"},
        }),
    )
    assert any("không khớp URL" in reason for reason in substituted)


# ── error type ────────────────────────────────────────────────────────────────
def test_error_collects_all_reasons():
    reasons = validate_order_payload(
        make_payload(budget=-1, placements=["ZN-999"], objective="nope"),
        make_ctx(),
    )
    assert len(reasons) >= 3
    err = OrderValidationError(reasons)
    msg = err.as_user_message()
    assert msg.startswith("⚠") and msg.count("- ") >= 3
