import json

import pytest


class _FakeResponse:
    def __init__(self, parsed):
        self.output_parsed = parsed


class _FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.kwargs = None

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        return _FakeResponse(self.parsed)


class _FakeClient:
    def __init__(self, parsed):
        self.responses = _FakeResponses(parsed)


@pytest.mark.asyncio
async def test_semantic_decision_uses_locked_openai_model_and_context():
    from openai_campaign.decision import decide_turn
    from openai_campaign.schemas import TurnDecision

    parsed = TurnDecision(
        turn_type="mixed",
        user_goal="Check availability and propose selecting the zone",
        subrequests=[
            {
                "kind": "read",
                "description": "Check next week's availability",
                "requires_live_data": True,
                "requested_capability": "get_zone_availability",
            },
            {
                "kind": "mutation",
                "description": "Select the zone if available",
                "requires_live_data": False,
                "requested_capability": "select_zone",
            },
        ],
        faq_scope="live_system",
        workflow_action="select_zone",
        entities=[{"type": "zone", "value": "the second one"}],
        would_mutate_workspace=True,
        confidence=0.93,
    )
    client = _FakeClient(parsed)

    decision = await decide_turn(
        session_id="semantic-model-lock",
        message="Is the second one free next week? If it is, use that.",
        history=[
            {"role": "assistant", "content": "I found three ZNews placements."},
        ],
        step=3,
        workspace={"revision": 7, "setup": {"selectedZoneIds": []}},
        pending_proposal=None,
        allowed_capabilities=["get_zone_availability", "select_zone"],
        client=client,
    )

    assert decision.turn_type == "mixed"
    assert decision.would_mutate_workspace is True
    call = client.responses.kwargs
    assert call["model"] == "gpt-5.4-mini"
    assert call["store"] is False
    payload = json.loads(call["input"])
    assert payload["recent_messages"][0]["content"].startswith("I found three")
    assert payload["current_step"] == 3
    assert payload["allowed_capabilities"] == [
        "get_zone_availability", "select_zone"
    ]


def test_low_confidence_semantic_decision_requires_clarification():
    from openai_campaign.schemas import TurnDecision

    decision = TurnDecision(
        turn_type="workflow_action",
        user_goal="Do an unresolved action",
        workflow_action="other",
        would_mutate_workspace=True,
        confidence=0.4,
    )
    assert decision.requires_clarification() is True


def test_turn_schema_preserves_question_and_mutation_as_separate_subrequests():
    from openai_campaign.schemas import TurnDecision

    decision = TurnDecision.model_validate({
        "turn_type": "mixed",
        "user_goal": "Answer and then propose a change",
        "subrequests": [
            {"kind": "question", "description": "Explain the audience"},
            {"kind": "mutation", "description": "Select that audience"},
        ],
        "faq_scope": "catalog_discovery",
        "workflow_action": "select_audience",
        "would_mutate_workspace": True,
        "confidence": 0.9,
    })
    assert [item.kind for item in decision.subrequests] == ["question", "mutation"]
