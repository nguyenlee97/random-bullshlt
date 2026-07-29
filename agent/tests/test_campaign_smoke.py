"""Safe campaign-flow smoke tests.

External LLM, catalog, and order APIs are replaced at their boundaries.  The
test therefore validates orchestration and persisted state without creating a
real campaign or consuming model credits.
"""
from datetime import date, timedelta

import pytest

from models import BriefData, CreativeData, CreativeFile, SegmentData, SetupData


@pytest.mark.parametrize(
    ("start_date", "expected"),
    [
        ("2026-07-20", "active"),
        ("2026-07-21", "active"),
        ("2026-07-22", "pending"),
        ("not-a-date", "pending"),
    ],
)
def test_initial_order_status_uses_campaign_date(start_date, expected):
    from handlers.setup import initial_order_status

    assert initial_order_status(
        start_date, today=date(2026, 7, 21),
    ) == expected


@pytest.mark.asyncio
async def test_campaign_form_flow_persists_state_and_creates_one_guarded_order(monkeypatch):
    import handlers.audience as audience_handler
    import handlers.brief as brief_handler
    import handlers.setup as setup_handler
    import validation.order_guard as order_guard
    from handlers.creative import handle_creative
    from session import get_or_create_session

    monkeypatch.setattr(
        brief_handler,
        "simple_generate",
        lambda *_: '{"summary":"Brief accepted","audience_hint":[],"warnings":[]}',
    )
    monkeypatch.setattr(
        audience_handler,
        "simple_generate",
        lambda *_: '{"reasoning":"Good fit","match_quality":"good","segment_notes":[],"warnings":[]}',
    )

    guarded_payloads = []

    async def fake_guard(payload, _session):
        guarded_payloads.append(payload)

    async def fake_create(payload):
        assert payload is guarded_payloads[-1]
        return {"id": "ORD-SMOKE-001", "status": "pending"}

    monkeypatch.setattr(order_guard, "guard_order", fake_guard)
    monkeypatch.setattr(setup_handler, "create_order", fake_create)
    monkeypatch.setattr("config.config.USE_VLM_CREATIVE", False)

    sid = "smoke_campaign_flow"
    tomorrow = date.today() + timedelta(days=1)
    end = tomorrow + timedelta(days=14)

    brief_response = await brief_handler.handle_brief(
        BriefData(
            brand="Smoke Test Brand",
            objective="awareness",
            kpi="Reach",
            budget=100,
            startDate=tomorrow.isoformat(),
            endDate=end.isoformat(),
            notes="Young gamers",
        ),
        sid,
    )
    assert brief_response.meta.tool == "brief_handler"

    segment = {
        "_id": "dmp-smoke-1",
        "fullLabel": "Young gamers",
        "type": "interest",
        "sizeMin": 100_000,
        "sizeMax": 200_000,
    }
    audience_response = await audience_handler.handle_audience(
        SegmentData(attrs=[segment]), sid
    )
    assert audience_response.meta.tool == "audience_handler"

    creative_response = await handle_creative(
        CreativeData(
            files=[
                CreativeFile(
                    name="banner.png",
                    type="image/png",
                    size=250_000,
                    width=1200,
                    height=628,
                    url="http://localhost:3000/uploads/banner.png",
                )
            ]
        ),
        sid,
    )
    assert creative_response.meta.tool == "creative_validate"

    order_response = await setup_handler.handle_setup(
        SetupData(
            phase=2,
            selectedZoneIds=["ZN-001"],
            assignments={"ZN-001": 0},
            fileUrls={"0": "http://localhost:3000/uploads/banner.png"},
            idempotencyKey="smoke-idempotency-key",
        ),
        sid,
    )

    assert order_response.meta.tool == "order_create"
    assert "ORD-SMOKE-001" in order_response.text
    assert len(guarded_payloads) == 1
    assert guarded_payloads[0]["idempotencyKey"] == "smoke-idempotency-key"

    session = await get_or_create_session(sid)
    assert session["form_state"]["brief"]["brand"] == "Smoke Test Brand"
    assert session["form_state"]["segment"]["attrs"][0]["_id"] == "dmp-smoke-1"
    assert session["form_state"]["creative"]["files"][0]["name"] == "banner.png"
    assert session["created_order_ids"] == ["ORD-SMOKE-001"]


@pytest.mark.asyncio
async def test_setup_entry_persists_proactive_message(monkeypatch):
    import handlers.setup as setup_handler
    import tools.order_api as order_api
    import tools.zone_catalog as zone_catalog
    from session import get_history, update_form_state

    zone = {
        "id": "ZN-001",
        "name": "Top banner",
        "reach": 1_000_000,
        "vi": 80,
        "ctr": 1.2,
        "cpm": 20_000,
        "reason": "High reach",
    }

    async def fake_zones():
        return [zone]

    async def fake_conflicts(*_):
        return {}

    async def fake_rank(**_):
        return [dict(zone)]

    monkeypatch.setattr(zone_catalog, "get_all_zones", fake_zones)
    monkeypatch.setattr(order_api, "fetch_zone_conflicts", fake_conflicts)
    monkeypatch.setattr(setup_handler, "rank_zones", fake_rank)

    sid = "setup_entry_history"
    await update_form_state(
        sid,
        "brief",
        {
            "brand": "History Brand",
            "objective": "awareness",
            "kpi": "Reach",
            "budget": 50,
            "startDate": "2030-01-01",
            "endDate": "2030-01-15",
        },
    )

    result = await setup_handler.handle_setup_entry(sid)
    history = await get_history(sid)

    assert result["skip"] is False
    assert history[-1] == {"role": "assistant", "content": result["text"]}


@pytest.mark.asyncio
async def test_openai_setup_entry_returns_six_unselected_related_zones(monkeypatch):
    import handlers.setup as setup_handler
    import tools.order_api as order_api
    import tools.zone_catalog as zone_catalog
    from session import update_form_state

    zones = [
        {
            "id": f"ZN-{index:03d}",
            "name": f"Zone {index}",
            "reach": 1_000_000 - index,
            "vi": 80,
            "ctr": 1.2,
            "cpm": 20_000,
            "reason": "Context match",
            "topicId": "automotive_mobility" if index < 9 else "legacy_other",
            "recommendation_basis": {"context_match": index < 9},
        }
        for index in range(14)
    ]

    async def fake_zones():
        return zones

    async def fake_conflicts(*_):
        return {}

    async def fake_rank(**_):
        return [dict(zone) for zone in zones]

    monkeypatch.setattr(zone_catalog, "get_all_zones", fake_zones)
    monkeypatch.setattr(order_api, "fetch_zone_conflicts", fake_conflicts)
    monkeypatch.setattr(setup_handler, "rank_zones", fake_rank)

    sid = "openai_setup_related"
    await update_form_state(
        sid,
        "brief",
        {
            "brand": "Related Zone Brand",
            "objective": "awareness",
            "kpi": "Reach",
            "budget": 100,
            "startDate": "2030-01-01",
            "endDate": "2030-01-15",
        },
    )

    result = await setup_handler.handle_setup_entry(sid, include_related=True)
    proposal = result["blocks"][0]["changes"]["value"]

    assert len(proposal["recoZones"]) == 6
    assert len(proposal["relatedZones"]) == 6
    assert set(proposal["selectedZoneIds"]) == {
        zone["id"] for zone in proposal["recoZones"]
    }
    assert not set(proposal["selectedZoneIds"]) & {
        zone["id"] for zone in proposal["relatedZones"]
    }
    assert "6 ad zones liên quan" in result["text"]
