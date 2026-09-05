from zalo_incidents import parse_incident_reply
from copy import deepcopy
from unittest.mock import AsyncMock
import pytest


def test_incident_choice_requires_explicit_incident_code():
    assert parse_incident_reply("2") == (None, 2)
    assert parse_incident_reply("2 INC-A12F90") == ("INC-A12F90", 2)


def test_incident_code_is_case_insensitive_and_can_show_detail_without_choice():
    assert parse_incident_reply("cho tôi xem inc-bb1290") == ("INC-BB1290", None)


def test_campaign_identifiers_do_not_enter_incident_namespace():
    assert parse_incident_reply("pause ORD-2026-100") == (None, None)


@pytest.mark.asyncio
@pytest.mark.parametrize('message', ['Xác nhận', 'Xem report', 'Tạo campaign mới', 'FAQ'])
async def test_unrelated_chat_never_consumes_incident_context(message):
    from zalo_incidents import handle_incident_reply
    thread = {'thread_id': 'thread-a', 'active_campaign_id': 'ORD-OTHER',
              'pending_action': {'kind': 'autopilot_approval'}, 'recent_incident_refs': [{'incident_id': 'INC-A12F90'}]}
    before = deepcopy(thread)
    reply, after = await handle_incident_reply(thread, message)
    assert reply is None and after == before


@pytest.mark.asyncio
async def test_bare_number_with_pending_campaign_and_incident_fails_closed():
    from zalo_incidents import handle_incident_reply
    thread = {'thread_id': 'thread-a', 'active_campaign_id': 'ORD-OTHER',
              'pending_action': {'kind': 'choose_autopilot_mode'},
              'recent_incident_refs': [{'incident_id': 'INC-A12F90'}]}
    before = deepcopy(thread)
    reply, after = await handle_incident_reply(thread, '2')
    assert 'có thể trả lời' in reply
    assert '2 INC-A12F90' in reply
    assert 'Chưa thực hiện thao tác nào' in reply
    assert after == before


@pytest.mark.asyncio
async def test_bare_number_without_pending_campaign_does_not_inherit_alert():
    from zalo_incidents import handle_incident_reply
    thread = {'thread_id': 'thread-a', 'pending_action': None,
              'recent_incident_refs': [{'incident_id': 'INC-A12F90'}]}
    before = deepcopy(thread)
    reply, after = await handle_incident_reply(thread, '2')
    assert reply is None and after == before


@pytest.mark.asyncio
async def test_unmapped_provider_reply_with_bare_number_fails_closed(monkeypatch):
    import zalo_incidents
    monkeypatch.setattr(zalo_incidents, '_incident_from_reply', AsyncMock(return_value=None))
    thread = {'thread_id': 'thread-a', 'pending_action': None,
              'recent_incident_refs': [{'incident_id': 'INC-A12F90'}]}
    before = deepcopy(thread)
    reply, after = await zalo_incidents.handle_incident_reply(
        thread, '1', reply_to_message_id='provider-message-unknown',
    )
    assert 'provider chưa map được alert' in reply
    assert '1 INC-A12F90' in reply
    assert after == before


@pytest.mark.asyncio
async def test_alert_only_updates_incident_namespace_and_uses_stable_outbox_key(monkeypatch):
    import zalo_incidents as incidents
    import zalo_campaign_agent as channel
    import zalo_worker
    thread = {'thread_id': 'thread-a', 'active_campaign_id': 'ORD-OTHER',
              'pending_action': {'kind': 'autopilot_approval'}}
    before = deepcopy(thread)
    monkeypatch.setattr(incidents, '_threads_for_campaign', AsyncMock(return_value=[thread]))
    write = AsyncMock(side_effect=lambda original, fields: {**original, **fields})
    send = AsyncMock()
    monkeypatch.setattr(channel, '_update_thread', write)
    monkeypatch.setattr(zalo_worker, 'enqueue_text', send)
    incident = {'incident_id': 'INC-A12F90', 'title': 'CTR thấp', 'scope': 'zone-a',
                'investigation': {'bundle_id': 'bundle-1', 'ambiguous': True,
                                  'top_hypothesis': {'label': 'Creative', 'confidence': 80}}}
    await incidents.notify_incidents('ORD-1', [incident], 2)
    await incidents.notify_incidents('ORD-1', [incident], 2)
    assert thread == before
    assert all(set(call.args[1]) == {'recent_incident_refs'} for call in write.call_args_list)
    assert send.call_args_list[0].kwargs['idempotency_key'] == send.call_args_list[1].kwargs['idempotency_key']
    assert '80%' not in send.call_args.kwargs['text']
    assert 'chưa kết luận' in send.call_args.kwargs['text']


def test_l2_alert_exposes_completion_partial_roles_and_evidence_ids():
    from zalo_incidents import _alert_text
    incident = {'incident_id': 'INC-A12F90', 'title': 'CTR thấp', 'scope': 'zone-a',
                'investigation': {'mode': 'multi_agent', 'cause_status': 'unresolved',
                                  'summary': 'Còn nhiều giả thuyết.',
                                  'completion': {'completed_roles': 2, 'total_roles': 4, 'unavailable_probes': 1},
                                  'tasks': {'performance': {'role': 'performance', 'status': 'completed',
                                                            'execution_status': 'completed', 'evidence_status': 'sufficient'},
                                            'placement': {'role': 'placement', 'status': 'completed',
                                                          'execution_status': 'completed', 'evidence_status': 'unavailable'}},
                                  'review': {'evidence_ids': ['EVD-001', 'EVD-002']},
                                  'limitations': ['Thiếu publisher probe.']}}
    text = _alert_text('ORD-1', incident)
    assert '2/4 vai trò hoàn tất' in text
    assert '1 probe không có dữ liệu' in text
    assert 'Chưa hoàn tất' not in text
    assert 'Evidence chưa đủ: placement: unavailable' in text
    assert 'EVD-001, EVD-002' in text


@pytest.mark.asyncio
async def test_zalo_l3_does_not_replace_pending_campaign_action(monkeypatch):
    import zalo_incidents as incidents
    import zalo_campaign_agent as channel
    import evaluation.store as store
    monkeypatch.setattr(channel, 'owned_campaigns', AsyncMock(return_value=[{'campaign_id': 'ORD-1'}]))
    monkeypatch.setattr(store, 'list_incidents', AsyncMock(return_value=[
        {'incident_id': 'INC-A12F90', 'campaign_id': 'ORD-1'}]))
    update = AsyncMock()
    monkeypatch.setattr(channel, '_update_thread', update)
    thread = {'pending_action': {'kind': 'autopilot_approval'}, 'active_campaign_id': 'ORD-OTHER'}
    before = deepcopy(thread)
    text, after = await incidents.handle_incident_reply(thread, '3 INC-A12F90')
    assert 'L3 chưa được mở' in text and after == before
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_old_recovery_confirmation_cancels_without_report_mutation(monkeypatch):
    import zalo_incidents as incidents
    import zalo_campaign_agent as channel
    import evaluation.service as service
    report = AsyncMock()
    monkeypatch.setattr(service, 'report_request', report)
    monkeypatch.setattr(channel, '_update_thread', AsyncMock(side_effect=lambda t, f: {**t, **f}))
    thread = {'active_campaign_id': 'ORD-OTHER', 'pending_action': {
        'kind': 'incident_recovery', 'expires_at': '2000-01-01', 'incident_id': 'INC-A12F90'}}
    reply, after = await incidents.handle_incident_reply(thread, 'Xác nhận INC-A12F90')
    assert 'đã được hủy' in reply and after['pending_action'] is None
    assert after['active_campaign_id'] == 'ORD-OTHER'
    report.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('message,reply_id', [('4 INC-A12F90 INC-BB1290', None), ('4 INC-A12F90', 'INC-BB1290')])
async def test_ambiguous_codes_never_mutate(monkeypatch, message, reply_id):
    import zalo_incidents as incidents
    import evaluation.store as store
    monkeypatch.setattr(incidents, '_incident_from_reply', AsyncMock(return_value=reply_id))
    mutate = AsyncMock()
    monkeypatch.setattr(store, 'transition_incident', mutate)
    text, _ = await incidents.handle_incident_reply({}, message, reply_to_message_id='provider-msg')
    assert 'chưa thực hiện thao tác' in text
    mutate.assert_not_awaited()


@pytest.mark.asyncio
async def test_freeform_question_not_prefix_dismiss_and_uses_shared_qa(monkeypatch):
    import zalo_incidents as incidents
    import zalo_campaign_agent as channel
    import evaluation.store as store
    from evaluation import questions
    incident = {'incident_id': 'INC-A12F90', 'campaign_id': 'ORD-1', 'dataset_revision': 2, 'investigation': {'bundle_id': 'b2'}}
    monkeypatch.setattr(channel, 'owned_campaigns', AsyncMock(return_value=[{'campaign_id': 'ORD-1'}]))
    monkeypatch.setattr(store, 'list_incidents', AsyncMock(return_value=[incident]))
    mutate = AsyncMock()
    monkeypatch.setattr(store, 'transition_incident', mutate)
    ask = AsyncMock(return_value={'answer': 'Chỉ giải thích.', 'citations': [], 'dataset_revision': 2, 'notice': 'Chỉ đọc.'})
    monkeypatch.setattr(questions, 'answer', ask)
    thread = {'thread_id': 't1', 'active_campaign_id': 'ORD-OTHER', 'pending_action': {'kind': 'autopilot_approval'}}
    before = deepcopy(thread)
    text, after = await incidents.handle_incident_reply(thread, '4 INC-A12F90 là gì?', external_event_id='msg-1')
    assert 'Chỉ giải thích' in text and after == before
    assert ask.call_args.args == ('ORD-1', 'INC-A12F90')
    assert ask.call_args.kwargs['channel'] == 'zalo:t1'
    mutate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('openai_enabled', [True, False])
async def test_incident_does_not_enter_campaign_histories_or_roll_session(monkeypatch, openai_enabled):
    import zalo_incidents, zalo_campaign_agent, zalo_sessions, session
    from config import config
    monkeypatch.setattr(config, 'ZALO_OPENAI_ENABLED', openai_enabled)
    thread = {'thread_id': 't1', 'pending_action': {'kind': 'autopilot_approval'}}
    monkeypatch.setattr(zalo_campaign_agent, 'get_or_create_thread', AsyncMock(return_value=thread))
    monkeypatch.setattr(zalo_incidents, 'handle_incident_reply', AsyncMock(return_value=('Incident answer', thread)))
    roll, append, add = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(zalo_sessions, 'get_or_roll_chat_session', roll)
    monkeypatch.setattr(zalo_sessions, 'append_chat_message', append)
    monkeypatch.setattr(session, 'add_message', add)
    result = await zalo_campaign_agent.handle_channel_event({'external_uid': 'u', 'event_name': 'user_send_text', 'text': 'Vì sao INC-A12F90?'})
    assert result == ['Incident answer']
    roll.assert_not_awaited(); append.assert_not_awaited(); add.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('message', ['FAQ', 'Xem report', 'Tạo campaign mới', 'Xác nhận'])
async def test_explicit_campaign_flow_switch_overrides_provider_reply(monkeypatch, message):
    import zalo_incidents
    lookup = AsyncMock(return_value='INC-A12F90')
    monkeypatch.setattr(zalo_incidents, '_incident_from_reply', lookup)
    result, thread = await zalo_incidents.handle_incident_reply({}, message, reply_to_message_id='alert-msg')
    assert result is None
    lookup.assert_not_awaited()
