"""Server-owned validation and causal scope, independent of model prose.

Codes are safe to persist: never store raw provider exceptions/model inputs.
An observed symptom is not a supported cause; local fixtures are not publishers.
"""
from copy import deepcopy

from pydantic import ValidationError

ERROR_MESSAGES = {
    'invalid_schema': 'Model decision did not match the required schema.',
    'invalid_action': 'Action is not allowed in this decision phase.',
    'unauthorized_tool': 'Tool is not authorized for this specialist.',
    'duplicate_tool': 'Tool was already collected; use existing evidence.',
    'finish_required': 'Collection budget reached; a final answer is required.',
    'required_evidence': 'Creative investigation must collect inspect_render and creative_compatibility before finishing; unavailable is an acceptable observation, not healthy evidence.',
    'unknown_evidence': 'Citation was not in the evidence supplied to this role.',
    'invalid_finish_target': 'A final answer must have an empty target.',
    'missing_summary': 'A final answer must contain a finding or explicit uncertainty.',
    'unsupported_cause': 'Selected cause lacks the required independently observed evidence.',
    'invalid_evidence_relation': 'Evidence relation does not match the allowed relationship for that hypothesis; use the supplied relation map.',
    'model_refusal': 'Provider refused the structured response.',
    'model_incomplete': 'Provider did not return a complete structured response.',
    'model_timeout': 'Provider response timed out.',
    'model_unavailable': 'Provider call failed; no conclusion was fabricated.',
    'decision_failed': 'Investigation decision failed.',
    'tool_timeout': 'Read-only evidence tool timed out.',
    'tool_failed': 'Read-only evidence tool failed.',
}


class DecisionError(ValueError):
    def __init__(self, code, *, repairable=False):
        self.code = code
        self.repairable = repairable
        super().__init__(ERROR_MESSAGES[code])


class ModelResponseError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(ERROR_MESSAGES[code])


def failure(exc):
    code = getattr(exc, 'code', 'decision_failed')
    if code not in ERROR_MESSAGES:
        code = 'decision_failed'
    return {'error_code': code, 'error': ERROR_MESSAGES[code]}


def parse_decision(raw):
    from evaluation.agent_model import Decision
    try:
        return Decision.model_validate(raw).model_dump()
    except ValidationError as exc:
        raise DecisionError('invalid_schema', repairable=True) from exc


def _cause_scope(code, cited):
    for item in cited:
        probe, finding = item.get('probe_id'), item.get('finding')
        if code == 'click_obstruction' and probe == 'inspect_render' and item.get('source') == 'isolated_browser_observation':
            observed = item.get('evidence') or {}
            points = observed.get('points') or []
            if (finding == 'hit_target_mismatch' and observed.get('visible')
                    and points and points[0].get('reaches_creative') is False
                    and observed.get('local_clicks_before') == observed.get('local_clicks_after') == 0):
                return 'isolated_document'
        if code == 'creative_contract_mismatch' and probe == 'creative_compatibility' and item.get('source') == 'derived':
            if finding in {'size_mismatch', 'format_mismatch'}:
                return 'creative_metadata'
        if code == 'configuration_drift' and probe == 'config_drift' and item.get('source') == 'derived':
            if finding == 'field_changed':
                return 'baseline_order_comparison'
    return 'unknown'


SCOPE_LIMITS = {
    'unknown': 'Chưa xác định nguyên nhân; xác nhận triệu chứng không đồng nghĩa đã tìm ra nguyên nhân.',
    'isolated_document': 'Chỉ quan sát tài liệu thử nghiệm cô lập; chưa kiểm chứng publisher hoặc quan hệ nhân quả với CTR thực tế.',
    'creative_metadata': 'Chỉ đối chiếu metadata creative/catalog; chưa chứng minh lỗi này gây ra CTR giảm.',
    'baseline_order_comparison': 'So với snapshot report baseline, không phải cấu hình đã ký duyệt; chưa chứng minh tác động lên KPI.',
}


def validated_finish(raw, evidence, *, typed=False):
    result = deepcopy(raw)
    if result.get('target'):
        raise DecisionError('invalid_finish_target', repairable=True)
    if not str(result.get('summary') or '').strip():
        raise DecisionError('missing_summary', repairable=True)
    refs = list(dict.fromkeys(result.get('evidence_ids') or []))
    counter = list(dict.fromkeys(result.get('counter_evidence_ids') or []))
    if any(ref not in evidence for ref in refs + counter):
        raise DecisionError('unknown_evidence', repairable=True)
    usable = [evidence[ref] for ref in refs if evidence[ref].get('status') != 'unavailable']
    cause = result.get('cause_code', 'none')
    scope = _cause_scope(cause, usable) if cause != 'none' else 'unknown'
    if cause != 'none' and scope == 'unknown':
        raise DecisionError('unsupported_cause', repairable=True)
    if typed:
        from evaluation.evidence_relations import normalize_finish
        return normalize_finish(result, evidence)
    result.update(evidence_ids=refs, counter_evidence_ids=counter, cause_code=cause, claim_scope=scope)
    if not usable:
        result.update(assessment='insufficient_evidence', summary='Chưa đủ bằng chứng đã kiểm tra để kết luận.')
    elif cause == 'none' and result['assessment'] == 'supported_hypothesis':
        result['assessment'] = 'ambiguous'
    if result.get('contradictions') or counter:
        if result['assessment'] == 'supported_hypothesis':
            result['assessment'] = 'ambiguous'
    result['cause_status'] = ('supported_hypothesis' if result['assessment'] == 'supported_hypothesis'
                              else 'insufficient_evidence' if not usable else 'unresolved')
    result['limitations'] = list(dict.fromkeys([SCOPE_LIMITS[scope]] + (result.get('limitations') or [])))[:8]
    return result
