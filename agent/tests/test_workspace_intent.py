import pytest

from graph.nodes import workspace_intent as intent_node
from graph.nodes.intercepts import intercepts_node
from workspace.intent import (
    InvalidWorkspaceIntent,
    WorkspaceIntent,
    classify_workspace_intent,
    looks_like_brief_edit,
    resolve_legacy_update,
    resolve_workspace_intent,
    validate_workspace_intent,
)
from workspace.service import get_workspace


def _change(**overrides) -> WorkspaceIntent:
    values = {
        "intent": "propose_change",
        "command": "set_brief_field",
        "field": "brief.brand",
        "value": "Thương Hiệu Mới",
        "reason": "Người dùng yêu cầu đổi brand",
        "confidence": 0.99,
        "requires_clarification": False,
        "clarification": "",
    }
    values.update(overrides)
    return WorkspaceIntent(**values)


def test_prefilter_targets_edits_but_not_normal_workspace_questions():
    assert looks_like_brief_edit(
        "Hãy đề xuất đổi brand trong workspace thành Thương Hiệu Mới"
    )
    assert not looks_like_brief_edit("Brand hiện tại trong workspace là gì?")
    assert not looks_like_brief_edit("Audience nào phù hợp với chiến dịch?")
    assert looks_like_brief_edit("Chuyển objective sang conversion")
    assert looks_like_brief_edit("Nhờ em thay tên thương hiệu thành Mây Xanh")
    assert looks_like_brief_edit("Chọn thêm ZingNews_PrBox_2")
    assert looks_like_brief_edit("Chỉ giữ lại creative square.png")


@pytest.mark.asyncio
async def test_normal_question_bypasses_the_structured_model(monkeypatch):
    def should_not_run(*args, **kwargs):
        raise AssertionError("structured model should have been bypassed")

    monkeypatch.setattr("workspace.intent._classify_sync", should_not_run)
    result = await classify_workspace_intent("Brand hiện tại là gì?", {"brand": "A"})
    assert result is None


def test_validator_merges_partial_brief_without_dropping_existing_fields():
    command = validate_workspace_intent(
        _change(field="brief", value={"brand": "B", "budget": 25}),
        {"brand": "A", "objective": "awareness", "budget": 10},
    )
    assert command == (
        "brief",
        {"brand": "B", "objective": "awareness", "budget": 25},
        "Người dùng yêu cầu đổi brand",
    )


@pytest.mark.parametrize(
    ("field", "raw", "expected"),
    [
        ("brief.startDate", "29/07/2026", "2026-07-29"),
        (
            "brief.endDate",
            "ng\u00e0y 5 th\u00e1ng 8 n\u0103m 2026",
            "2026-08-05",
        ),
    ],
)
def test_validator_normalizes_localized_brief_date_edits(field, raw, expected):
    current = {
        "brand": "A",
        "objective": "awareness",
        "budget": 10,
        "startDate": "2026-07-29",
        "endDate": "2026-08-05",
    }
    command = validate_workspace_intent(
        _change(field=field, value=raw),
        current,
    )
    assert command[0] == field
    assert command[1] == expected


def test_validator_rejects_invalid_or_hallucinated_values():
    with pytest.raises(InvalidWorkspaceIntent):
        validate_workspace_intent(
            _change(field="brief.objective", value="make_everything_viral"), {}
        )
    with pytest.raises(InvalidWorkspaceIntent):
        validate_workspace_intent(
            _change(field="brief", value={"secretAdminFlag": True}), {}
        )


@pytest.mark.asyncio
async def test_explicit_edit_creates_durable_proposal_without_mutating(monkeypatch):
    async def classified(message, current_brief):
        return _change()

    monkeypatch.setattr(intent_node, "classify_workspace_intent", classified)
    result = await intent_node.workspace_intent_node({
        "session_id": "intent-proposal",
        "step": 0,
        "user_message": "đổi brand thành Thương Hiệu Mới",
        "workspace": {},
        "confirmed_steps": [],
    })

    assert result["used_tool"] == "workspace_proposal"
    block = result["response_blocks"][0]
    assert block["type"] == "workspace_proposal"
    assert block["changes"]["proposal_id"].startswith("wpr_")
    assert block["changes"]["field"] == "brief.brand"

    before_approval = await get_workspace("intent-proposal")
    assert before_approval["revision"] == 0
    assert before_approval["artifacts"]["brief"]["value"] is None

    confirmed = await intercepts_node({
        "session_id": "intent-proposal",
        "step": 0,
        "user_message": "đồng ý",
        "workspace": {},
    })
    assert confirmed["workspace_update"]["proposal_id"] == block["changes"]["proposal_id"]
    after_approval = await get_workspace("intent-proposal")
    assert after_approval["revision"] == 1
    assert after_approval["artifacts"]["brief"]["value"]["brand"] == "Thương Hiệu Mới"


@pytest.mark.asyncio
async def test_structured_brief_proposal_preserves_omitted_audience_notes(monkeypatch):
    message = (
        "Thiết lập brief ZaloPay Summer, ngân sách 40 triệu. "
        "Đối tượng 20-35 tại TP.HCM, quan tâm công nghệ và thanh toán số."
    )

    async def classified(_message, _workspace):
        return _change(
            command="set_brief_fields",
            field="brief",
            value={
                "brand": "ZaloPay Summer",
                "objective": "awareness",
                "kpi": "Reach",
                "budget": 40,
                "startDate": "2026-08-01",
                "endDate": "2026-08-31",
            },
        )

    monkeypatch.setattr(intent_node, "classify_workspace_intent", classified)
    result = await intent_node.workspace_intent_node({
        "session_id": "intent-preserve-notes",
        "step": 0,
        "user_message": message,
        "workspace": {},
        "confirmed_steps": [],
    })

    assert result["response_blocks"][0]["changes"]["value"]["notes"] == message


@pytest.mark.asyncio
async def test_ambiguous_edit_asks_for_value_and_does_not_create_proposal(monkeypatch):
    async def classified(message, current_brief):
        return _change(
            field="none",
            value=None,
            requires_clarification=True,
            clarification="Anh/chị muốn đổi brand thành tên nào?",
        )

    monkeypatch.setattr(intent_node, "classify_workspace_intent", classified)
    result = await intent_node.workspace_intent_node({
        "session_id": "intent-clarify",
        "step": 0,
        "user_message": "đổi brand",
        "workspace": {},
        "confirmed_steps": [],
    })
    assert result["used_tool"] == "workspace_clarification"
    assert "tên nào" in result["response_text"]
    workspace = await get_workspace("intent-clarify")
    assert workspace["revision"] == 0


def _workspace(**values):
    artifacts = {
        name: {"status": "missing", "revision": 0, "value": None}
        for name in (
            "brief", "audience", "targeting", "creative", "placements",
            "assignments",
        )
    }
    for name, value in values.items():
        artifacts[name] = {"status": "approved", "revision": 1, "value": value}
    return {"revision": 1, "artifacts": artifacts}


def _command(command, field, value, operation="replace"):
    return WorkspaceIntent(
        intent="propose_change",
        command=command,
        field=field,
        operation=operation,
        value=value,
        reason="requested",
        confidence=0.99,
    )


@pytest.mark.asyncio
async def test_audience_command_resolves_only_authoritative_segments(monkeypatch):
    catalog = [
        {"_id": "mongo-1", "segmentId": "INT001", "fullLabel": "Travel", "sizeMin": 100, "sizeMax": 200},
        {"_id": "mongo-2", "segmentId": "BEH001", "fullLabel": "Online Gamers", "sizeMin": 200, "sizeMax": 400},
    ]

    async def all_segments(limit=500):
        return catalog

    monkeypatch.setattr("workspace.intent.get_all_segments", all_segments)
    result = await resolve_workspace_intent(
        _command("select_audience_segments", "segment", ["INT001", "Online Gamers"]),
        _workspace(),
    )
    assert result[0] == "segment"
    assert [item["_id"] for item in result[1]["attrs"]] == ["mongo-1", "mongo-2"]
    assert result[1]["size"] > 0


@pytest.mark.asyncio
async def test_audience_command_rejects_unknown_model_id(monkeypatch):
    async def all_segments(limit=500):
        return [{"_id": "real", "segmentId": "INT001", "fullLabel": "Travel"}]

    async def no_suggestions(query, limit=3):
        return []

    monkeypatch.setattr("workspace.intent.get_all_segments", all_segments)
    monkeypatch.setattr("workspace.intent.search_audience", no_suggestions)
    with pytest.raises(InvalidWorkspaceIntent, match="Không tìm thấy segment"):
        await resolve_workspace_intent(
            _command("select_audience_segments", "segment", ["FAKE-999"]),
            _workspace(),
        )


@pytest.mark.asyncio
async def test_audience_remove_resolves_ambiguous_label_within_current_selection(monkeypatch):
    current = {"_id": "selected-travel", "segmentId": "BEH001", "fullLabel": "Travel"}

    async def all_segments(limit=500):
        return [
            current,
            {"_id": "other-travel", "segmentId": "INT999", "fullLabel": "Travel"},
        ]

    monkeypatch.setattr("workspace.intent.get_all_segments", all_segments)
    result = await resolve_workspace_intent(
        _command("select_audience_segments", "segment", ["Travel"], "remove"),
        _workspace(audience={"attrs": [current], "size": 100}),
    )
    assert result[1]["attrs"] == []
    assert result[1]["size"] == 0


@pytest.mark.asyncio
async def test_targeting_command_validates_and_preserves_other_dimensions(monkeypatch):
    async def options():
        return {
            "geo": {"Miền Nam": ["TP.HCM", "Cần Thơ"]},
            "age": ["18-24", "25-34"],
            "gender": ["Male", "Female"],
        }

    monkeypatch.setattr("workspace.intent.get_targeting_options", options)
    result = await resolve_workspace_intent(
        _command(
            "set_targeting_rules", "targeting", {"geo": ["tp.hcm"]}, "replace"
        ),
        _workspace(targeting={"age": ["25-34"], "gender": ["Female"]}),
    )
    assert result[1] == {
        "age": ["25-34"], "gender": ["Female"], "geo": ["TP.HCM"]
    }


@pytest.mark.asyncio
async def test_targeting_command_rejects_non_catalog_value(monkeypatch):
    async def options():
        return {"age": ["18-24", "25-34"]}

    monkeypatch.setattr("workspace.intent.get_targeting_options", options)
    with pytest.raises(InvalidWorkspaceIntent, match="không có trong catalog"):
        await resolve_workspace_intent(
            _command("set_targeting_rules", "targeting", {"age": ["19-29"]}),
            _workspace(),
        )


@pytest.mark.asyncio
async def test_placement_command_checks_catalog_and_booking_conflicts(monkeypatch):
    zones = [{"id": "ZONE-A"}, {"id": "ZONE-B"}]

    async def all_zones():
        return zones

    async def no_conflicts(start, end):
        return {}

    monkeypatch.setattr("workspace.intent.get_all_zones", all_zones)
    monkeypatch.setattr("workspace.intent.fetch_zone_conflicts", no_conflicts)
    result = await resolve_workspace_intent(
        _command("select_placements", "setup.selectedZoneIds", ["ZONE-B"], "add"),
        _workspace(
            brief={"startDate": "2026-08-01", "endDate": "2026-08-10"},
            placements={"selectedZoneIds": ["ZONE-A"], "phase": "zones"},
        ),
    )
    assert result[0] == "setup.selectedZoneIds"
    assert result[1] == ["ZONE-A", "ZONE-B"]

    async def booked(start, end):
        return {"ZONE-B": {"orderId": "ORD-1"}}

    monkeypatch.setattr("workspace.intent.fetch_zone_conflicts", booked)
    with pytest.raises(InvalidWorkspaceIntent, match="đã được đặt"):
        await resolve_workspace_intent(
            _command("select_placements", "setup.selectedZoneIds", ["ZONE-B"]),
            _workspace(
                brief={"startDate": "2026-08-01", "endDate": "2026-08-10"}
            ),
        )


@pytest.mark.asyncio
async def test_creative_command_can_remove_but_never_invent_uploads():
    files = [
        {"id": "file-1", "name": "hero.png", "analysisId": "ana-1"},
        {"id": "file-2", "name": "square.png", "analysisId": "ana-2"},
    ]
    result = await resolve_workspace_intent(
        _command("select_creative_files", "creative.files", ["hero.png"], "remove"),
        _workspace(creative={"files": files}),
    )
    assert result[1] == [files[1]]
    with pytest.raises(InvalidWorkspaceIntent, match="Không thể upload"):
        await resolve_workspace_intent(
            _command("select_creative_files", "creative.files", ["hero.png"], "add"),
            _workspace(creative={"files": files}),
        )


@pytest.mark.asyncio
async def test_assignment_command_resolves_selected_zone_and_file(monkeypatch):
    async def all_zones():
        return [{"id": "ZONE-A"}, {"id": "ZONE-B"}]

    monkeypatch.setattr("workspace.intent.get_all_zones", all_zones)
    files = [
        {"id": "file-1", "name": "hero.png"},
        {"id": "file-2", "name": "square.png"},
    ]
    result = await resolve_workspace_intent(
        _command(
            "set_assignments", "assignments", {"ZONE-B": "square.png"}, "set"
        ),
        _workspace(
            placements={"selectedZoneIds": ["ZONE-A", "ZONE-B"]},
            creative={"files": files},
            assignments={"ZONE-A": 0},
        ),
    )
    assert result[1] == {"ZONE-A": 0, "ZONE-B": 1}


@pytest.mark.asyncio
async def test_command_field_mismatch_is_rejected_before_proposal():
    with pytest.raises(InvalidWorkspaceIntent, match="audience"):
        await resolve_workspace_intent(
            _command("select_audience_segments", "targeting", ["INT001"]),
            _workspace(),
        )


@pytest.mark.asyncio
async def test_explicit_decline_is_terminal_and_never_calls_classifier(monkeypatch):
    async def should_not_run(*args, **kwargs):
        raise AssertionError("decline should bypass classifier")

    monkeypatch.setattr(intent_node, "classify_workspace_intent", should_not_run)
    result = await intent_node.workspace_intent_node({
        "session_id": "intent-decline", "step": 0,
        "user_message": "Không đồng ý đổi brand", "workspace": {},
        "confirmed_steps": [],
    })
    assert result["used_tool"] == "workspace_no_change"
    workspace = await get_workspace("intent-decline")
    assert workspace["revision"] == 0


@pytest.mark.asyncio
async def test_other_intent_with_missing_value_returns_structured_clarification(monkeypatch):
    async def classified(message, workspace):
        return WorkspaceIntent(
            intent="other", command="none", field="none", operation="none",
            value=None, confidence=0.98, requires_clarification=True,
            clarification="Bạn muốn ngân sách mới là bao nhiêu?",
        )

    monkeypatch.setattr(intent_node, "classify_workspace_intent", classified)
    result = await intent_node.workspace_intent_node({
        "session_id": "intent-missing-budget", "step": 0,
        "user_message": "Tôi muốn đổi ngân sách", "workspace": {},
        "confirmed_steps": [],
    })
    assert result["used_tool"] == "workspace_clarification"
    assert "bao nhiêu" in result["response_text"]


@pytest.mark.asyncio
async def test_assignment_remove_accepts_model_map_shape(monkeypatch):
    async def all_zones():
        return [{"id": "ZONE-A"}]

    monkeypatch.setattr("workspace.intent.get_all_zones", all_zones)
    result = await resolve_workspace_intent(
        _command(
            "set_assignments", "assignments", {"ZONE-A": 0}, "remove"
        ),
        _workspace(
            placements={"selectedZoneIds": ["ZONE-A"]},
            creative={"files": [{"id": "f1", "name": "hero.png"}]},
            assignments={"ZONE-A": 0},
        ),
    )
    assert result[1] == {}


@pytest.mark.asyncio
async def test_legacy_audience_payload_rejects_hallucinated_segment(monkeypatch):
    async def all_segments(limit=500):
        return [{"_id": "real-1", "segmentId": "INT001", "fullLabel": "Travel Lovers"}]

    async def no_suggestions(query, limit=3):
        return []

    monkeypatch.setattr("workspace.intent.get_all_segments", all_segments)
    monkeypatch.setattr("workspace.intent.search_audience", no_suggestions)
    with pytest.raises(InvalidWorkspaceIntent, match="FAKE-999"):
        await resolve_legacy_update(
            "segment",
            {"attrs": [{"_id": "FAKE-999", "fullLabel": "Invented Audience"}]},
            _workspace(),
        )


@pytest.mark.asyncio
async def test_legacy_creative_payload_cannot_invent_uploaded_file():
    workspace = _workspace(
        creative={"files": [{"id": "file-1", "name": "hero.png"}]}
    )
    with pytest.raises(InvalidWorkspaceIntent, match="creative hiện có"):
        await resolve_legacy_update(
            "creative",
            {"files": [{"id": "fake-file", "name": "invented.png"}]},
            workspace,
        )


@pytest.mark.asyncio
async def test_legacy_brief_payload_is_normalized_and_validated():
    result = await resolve_legacy_update(
        "brief",
        {
            "brand": "Zalo Ads",
            "objective": "conversion",
            "kpi": "1,000 leads",
            "budget": "250 triệu",
            "startDate": "2026-08-01",
            "endDate": "2026-08-31",
            "notes": "Hackathon demo",
        },
        _workspace(brief={"brand": "Old"}),
        "User supplied a complete brief",
    )
    assert result[0] == "brief"
    assert result[1]["budget"] == 250
    assert result[1]["brand"] == "Zalo Ads"


@pytest.mark.asyncio
async def test_legacy_brief_preserves_user_audience_context_when_model_omits_notes():
    message = (
        "Thiết lập brief ZaloPay Summer, ngân sách 40 triệu. "
        "Đối tượng 20-35 tại TP.HCM, quan tâm công nghệ và thanh toán số."
    )
    result = await resolve_legacy_update(
        "brief",
        {
            "brand": "ZaloPay Summer",
            "objective": "awareness",
            "kpi": "Reach",
            "budget": 40,
            "startDate": "2026-08-01",
            "endDate": "2026-08-31",
        },
        _workspace(),
        "User supplied a complete brief",
        source_message=message,
    )

    assert result[0] == "brief"
    assert result[1]["notes"] == message


@pytest.mark.asyncio
async def test_legacy_brief_keeps_model_notes_instead_of_raw_message():
    result = await resolve_legacy_update(
        "brief",
        {
            "brand": "ZaloPay Summer",
            "objective": "awareness",
            "kpi": "Reach",
            "budget": 40,
            "startDate": "2026-08-01",
            "endDate": "2026-08-31",
            "notes": "Audience: 20-35, fintech",
        },
        _workspace(),
        source_message="Đối tượng người trẻ tại TP.HCM",
    )

    assert result[1]["notes"] == "Audience: 20-35, fintech"


@pytest.mark.asyncio
async def test_legacy_setup_assignment_indices_resolve_to_current_files(monkeypatch):
    async def all_zones():
        return [{"id": "ZONE-A"}]

    monkeypatch.setattr("workspace.intent.get_all_zones", all_zones)
    result = await resolve_legacy_update(
        "setup",
        {"selectedZoneIds": ["ZONE-A"], "assignments": {"ZONE-A": 1}},
        _workspace(
            placements={"selectedZoneIds": ["ZONE-A"]},
            creative={"files": [
                {"id": "file-1", "name": "hero.png"},
                {"id": "file-2", "name": "square.png"},
            ]},
        ),
    )
    assert result == ("assignments", {"ZONE-A": 1}, "")


@pytest.mark.asyncio
async def test_legacy_setup_cannot_change_zones_and_assignments_atomically():
    with pytest.raises(InvalidWorkspaceIntent, match="từng thay đổi"):
        await resolve_legacy_update(
            "setup",
            {"selectedZoneIds": ["ZONE-B"], "assignments": {"ZONE-B": 0}},
            _workspace(
                placements={"selectedZoneIds": ["ZONE-A"]},
                creative={"files": [{"id": "file-1", "name": "hero.png"}]},
            ),
        )
