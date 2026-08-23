from zalo_incidents import parse_incident_reply


def test_incident_choice_requires_explicit_incident_code():
    assert parse_incident_reply("2") == (None, 2)
    assert parse_incident_reply("2 INC-A12F90") == ("INC-A12F90", 2)


def test_incident_code_is_case_insensitive_and_can_show_detail_without_choice():
    assert parse_incident_reply("cho tôi xem inc-bb1290") == ("INC-BB1290", None)


def test_campaign_identifiers_do_not_enter_incident_namespace():
    assert parse_incident_reply("pause ORD-2026-100") == (None, None)
