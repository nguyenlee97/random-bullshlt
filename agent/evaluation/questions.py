"""Evidence-grounded incident Q&A. No campaign tools, mutations or shared chat memory."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid
from urllib.parse import quote

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import config
from evaluation.agent_model import decide
from evaluation.decision_contract import DecisionError, parse_decision, validated_finish
from evaluation.evidence_tools import model_evidence
from evaluation.evidence_relations import VERSION as RELATION_VERSION, allowed_links
from evaluation.store import get_incident, get_policy
from evaluation.service import report_request


class QuestionError(RuntimeError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc)


async def collection():
    import session
    if not await session._ensure_mongo():
        raise QuestionError('Kho lưu hỏi đáp chưa sẵn sàng. Chưa gọi model.', 503)
    return session._client[config.MONGODB_DB]['evaluation_incident_questions']


async def ensure_indexes():
    col = await collection()
    await col.create_index([('campaign_id', 1), ('incident_id', 1), ('created_at', -1)])


async def snapshot(campaign_id, incident_id, revision, bundle_id):
    incident = await get_incident(campaign_id, incident_id)
    if not incident:
        raise QuestionError('Không tìm thấy incident.', 404)
    policy = await get_policy(campaign_id)
    bundle = incident.get('investigation') or {}
    if not config.EVALUATION_MULTI_AGENT_ENABLED or not policy.get('enabled') or policy.get('level') not in {'L2', 'L3'}:
        raise QuestionError('Hỏi đáp evidence cần bật L2 multi-agent.', 403)
    if not bundle or bundle.get('mode') != 'multi_agent':
        raise QuestionError('Chưa có kết quả L2 multi-agent. Hãy chạy điều tra trước.')
    if (incident.get('dataset_revision') != revision or bundle.get('dataset_revision') != revision
            or bundle.get('bundle_id') != bundle_id or bundle.get('policy_version') != policy['version']
            or bundle.get('campaign_id') != campaign_id or bundle.get('incident_id') != incident_id):
        raise QuestionError('Kết quả điều tra đã thay đổi hoặc hết hạn. Hãy tải lại và điều tra revision hiện tại.')
    dataset = await report_request('GET', '/api/reports/internal/datasets/' + quote(campaign_id, safe=''))
    if (dataset.get('state') or {}).get('activeRevision') != revision:
        raise QuestionError('Dữ liệu report đã đổi. Hãy chạy Evaluation và điều tra revision mới trước khi hỏi.')
    if bundle.get('snapshot_signature'):
        from evaluation.investigator import build_context
        from evaluation.investigation_resume import snapshot_signature
        ctx = await build_context(campaign_id, incident, policy=policy, dataset=dataset)
        signature = snapshot_signature(bundle, ctx, (dataset.get('active') or {}).get('runtimeFixture'))
        if signature != bundle['snapshot_signature']:
            raise QuestionError('Order, catalog hoặc dữ liệu kiểm tra đã thay đổi. Hãy điều tra lại trước khi hỏi.')
    return incident, bundle, policy


async def answer(campaign_id: str, incident_id: str, *, question: str, request_id: str,
                 expected_revision: int, expected_bundle_id: str, channel='web') -> dict:
    """Caller must resolve ownership. Every answer/replay also checks current evidence."""
    question = question.strip()
    if not question or len(question) > 1200:
        raise QuestionError('Câu hỏi cần từ 1 đến 1200 ký tự.', 422)
    incident, bundle, policy = await snapshot(campaign_id, incident_id, expected_revision, expected_bundle_id)
    evidence = {e['evidence_id']: model_evidence(e) for e in bundle.get('probes', [])
                if e.get('evidence_id') and e.get('campaign_id') == campaign_id
                and e.get('scope') == incident.get('scope') and e.get('dataset_revision') == expected_revision}
    context = {'question': question, 'incident_id': incident_id, 'scope': incident.get('scope'),
               'title': incident.get('title'), 'dataset_revision': expected_revision,
               'assessment': bundle.get('assessment'), 'partial': bundle.get('partial', False),
               'cause_code': bundle.get('cause_code', 'none'), 'cause_status': bundle.get('cause_status', 'unresolved'),
               'claim_scope': bundle.get('claim_scope', 'unknown'), 'limitations': bundle.get('limitations', []),
               'investigation_summary': bundle.get('summary'), 'evidence': list(evidence.values())}
    typed = bundle.get('relationship_version') == RELATION_VERSION
    if typed:
        context.update(allowed_evidence_links=allowed_links(evidence), hypotheses=bundle.get('hypotheses', []))
    if len(json.dumps(context, ensure_ascii=False, default=str)) > 48000:
        raise QuestionError('Evidence vượt giới hạn hỏi đáp; hãy xem từng probe trong kết quả L2.', 422)
    key = 'IQ-' + hashlib.sha256(f'{channel}|{campaign_id}|{incident_id}|{request_id}'.encode()).hexdigest()
    fingerprint = hashlib.sha256(json.dumps([question, expected_revision, expected_bundle_id, policy['version']]).encode()).hexdigest()
    col = await collection()
    doc = {'campaign_id': campaign_id, 'incident_id': incident_id, 'question_id': key,
           'fingerprint': fingerprint, 'question': question, 'channel': channel,
           'policy_version': policy['version'], 'model': config.EVALUATION_AGENT_MODEL,
           'dataset_revision': expected_revision, 'bundle_id': expected_bundle_id,
           'status': 'queued', 'attempts': 0, 'created_at': now()}
    try:
        await col.update_one({'_id': key}, {'$setOnInsert': doc}, upsert=True)
    except DuplicateKeyError:
        pass
    existing = await col.find_one({'_id': key})
    if existing['fingerprint'] != fingerprint:
        raise QuestionError('Mã yêu cầu đã dùng cho câu hỏi hoặc revision khác.')
    if existing['status'] == 'completed':
        return existing['response']
    token = uuid.uuid4().hex
    claimed = await col.find_one_and_update(
        {'_id': key, 'attempts': {'$lt': 2}, '$or': [
            {'status': 'queued'}, {'status': 'failed'}, {'status': 'running', 'lease_until': {'$lte': now()}}]},
        {'$set': {'status': 'running', 'lease_token': token, 'lease_until': now() + timedelta(seconds=90)},
         '$inc': {'attempts': 1}}, return_document=ReturnDocument.AFTER)
    if not claimed:
        raise QuestionError('Câu hỏi đang được xử lý hoặc đã hết số lần thử; không gọi model trùng.')
    fence = {'_id': key, 'status': 'running', 'lease_token': token, 'lease_until': {'$gt': now()}}
    try:
        # A durable per-incident/revision ceiling also bounds fresh request IDs.
        budget_id = f'budget:{campaign_id}:{incident_id}:{expected_revision}'
        try:
            await col.update_one({'_id': budget_id}, {'$setOnInsert': {'calls': 0}}, upsert=True)
        except DuplicateKeyError:
            pass
        reserved = await col.find_one_and_update({'_id': budget_id, 'calls': {'$lt': 30}},
                    {'$inc': {'calls': 1}}, return_document=ReturnDocument.AFTER)
        if not reserved:
            raise QuestionError('Đã đạt giới hạn 30 lượt hỏi model cho incident/revision này.', 429)
        result = await asyncio.wait_for(decide('incident_qa', context, tools={}), timeout=45)
        refs = list(dict.fromkeys(result.get('evidence_ids') or []))
        if result.get('action') != 'finish' or any(ref not in evidence for ref in refs):
            raise QuestionError('Câu trả lời không vượt qua kiểm tra dẫn chứng. Chưa công bố kết quả.', 502)
        if not result.get('summary') or (not refs and result.get('assessment') != 'insufficient_evidence'):
            raise QuestionError('Câu trả lời thiếu dẫn chứng. Chưa công bố kết quả.', 502)
        try:
            result = validated_finish(parse_decision(result), evidence, typed=typed)
        except DecisionError as exc:
            raise QuestionError('Câu trả lời chưa hợp lệ: ' + exc.code + '. Chưa công bố kết quả.', 502) from exc
        if result['cause_code'] not in {'none', bundle.get('cause_code', 'none')}:
            raise QuestionError('Q&A không được tự thêm nguyên nhân ngoài kết quả điều tra.', 502)
        refreshed, _, _ = await snapshot(campaign_id, incident_id, expected_revision, expected_bundle_id)
        if refreshed.get('state') != incident.get('state'):
            raise QuestionError('Trạng thái incident đã đổi trong lúc trả lời. Hãy tải lại.')
        assessment = result['assessment']
        if assessment == 'supported_hypothesis' and (bundle.get('partial')
                or bundle.get('assessment') != 'supported_hypothesis'
                or not any(evidence[ref].get('status') == 'anomaly' for ref in refs)):
            assessment = 'ambiguous'
        answer_text = result['summary']
        if typed:
            # The model selects relevant owned observations, but cannot publish
            # unsupported causal exclusions in free-form Q&A prose.
            answer_text += '\n' + '\n'.join(f"{evidence[ref]['probe_id']}: {evidence[ref].get('summary', '')}" for ref in refs[:4])
        response = {'question_id': key, 'question': question, 'answer': answer_text,
                    'dataset_revision': expected_revision, 'bundle_id': expected_bundle_id,
                    'assessment': assessment, 'created_at': now().isoformat(),
                    'cause_code': result['cause_code'], 'claim_scope': result['claim_scope'],
                    'cause_status': 'supported_hypothesis' if assessment == 'supported_hypothesis' else 'unresolved',
                    'limitations': list(dict.fromkeys(bundle.get('limitations', []) + result['limitations']))[:8],
                    'citations': [{k: evidence[ref].get(k) for k in
                        ('evidence_id', 'probe_id', 'status', 'source', 'observed_at')} for ref in refs],
                    'notice': 'Hỏi đáp chỉ giải thích evidence; không thay đổi campaign và không thực thi recovery.'}
        fence['lease_until'] = {'$gt': now()}
        saved = await col.find_one_and_update(fence, {'$set': {'status': 'completed', 'response': response}},
                                            return_document=ReturnDocument.AFTER)
        if not saved:
            raise QuestionError('Yêu cầu đã hết lease. Chưa công bố câu trả lời.')
        return response
    except Exception as exc:
        fence['lease_until'] = {'$gt': now()}
        await col.update_one(fence, {'$set': {'status': 'failed', 'error_type': type(exc).__name__}})
        raise


async def history(campaign_id, incident_id):
    col = await collection()
    rows = await col.find({'campaign_id': campaign_id, 'incident_id': incident_id, 'status': 'completed'}).sort('created_at', -1).limit(20).to_list(None)
    # Historical answers always retain revision/bundle; never replay as current.
    return [r['response'] for r in reversed(rows)]
