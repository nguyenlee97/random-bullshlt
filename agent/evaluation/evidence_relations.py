"""Typed, server-owned relationships between observations and scoped hypotheses.

No scenario labels, probability scores or publisher causality. Model prose is
not a source of contradictions or a public causal verdict.
"""
from evaluation.decision_contract import DecisionError, SCOPE_LIMITS, _cause_scope

VERSION = 'evidence-relations-v1'
HYPOTHESES = {
    'click_obstruction': ('Vùng click bị che', 'isolated_document', 'inspect_render'),
    'creative_contract_mismatch': ('Creative không khớp placement', 'creative_metadata', 'creative_compatibility'),
    'configuration_drift': ('Cấu hình khác baseline', 'baseline_order_comparison', 'config_drift'),
}
RELATION_LABELS = {'supports': 'Hỗ trợ', 'contradicts': 'Phản bác trong phạm vi kiểm tra',
                   'context': 'Chỉ cung cấp bối cảnh', 'unavailable': 'Chưa kiểm chứng'}


def relation(code, item):
    if item.get('status') == 'unavailable':
        return 'unavailable'
    if _cause_scope(code, [item]) != 'unknown':
        return 'supports'
    probe, finding = item.get('probe_id'), item.get('finding')
    if code == 'click_obstruction' and probe == 'inspect_render' and item.get('source') == 'isolated_browser_observation':
        value = item.get('evidence') or {}
        points = value.get('points') or []
        before, after = value.get('local_clicks_before'), value.get('local_clicks_after')
        if (value.get('visible') and points and all(p.get('reaches_creative') is True for p in points)
                and isinstance(before, (int, float)) and isinstance(after, (int, float)) and after > before):
            return 'contradicts'
    if item.get('source') == 'derived':
        if code == 'creative_contract_mismatch' and probe == 'creative_compatibility' and finding == 'compatible':
            return 'contradicts'
        # A baseline comparison checks only its listed fields, never all config.
        if (code == 'configuration_drift' and probe == 'config_drift' and finding == 'matches_baseline'
                and (item.get('evidence') or {}).get('compared_fields')):
            return 'contradicts'
    return 'context'


def allowed_links(evidence):
    return [{'hypothesis_id': code, 'evidence_id': ref, 'relation': relation(code, item)}
            for code in HYPOTHESES for ref, item in evidence.items()]


def build_hypotheses(evidence):
    cards = []
    all_links = allowed_links(evidence)
    for code, (label, scope, probe) in HYPOTHESES.items():
        links = [x for x in all_links if x['hypothesis_id'] == code]
        support = [x['evidence_id'] for x in links if x['relation'] == 'supports']
        counter = [x['evidence_id'] for x in links if x['relation'] == 'contradicts']
        direct = [x for x in links if evidence[x['evidence_id']].get('probe_id') == probe]
        status = 'conflicting' if support and counter else 'supported' if support else 'contradicted' if counter else 'unknown'
        missing = [] if support or counter else [f'Cần bằng chứng phù hợp từ {probe}; dữ liệu hiện có chưa đủ kết luận.']
        if code == 'configuration_drift':
            fields = sorted({field for x in direct for field in (evidence[x['evidence_id']].get('evidence') or {}).get('missing_fields', [])})
            if fields:
                missing.append('Các trường chưa được đối chiếu: ' + ', '.join(fields) + '.')
        cards.append({'hypothesis_id': code, 'label': label, 'claim_scope': scope, 'status': status,
                      'supporting_evidence_ids': support, 'contradicting_evidence_ids': counter,
                      'evidence_links': links, 'missing_evidence': missing,
                      'limitations': [SCOPE_LIMITS[scope]], 'probe_collected': bool(direct),
                      'explanation': ('Có quan sát hỗ trợ trong phạm vi kiểm tra; chưa chứng minh nguyên nhân KPI.' if status == 'supported'
                                      else 'Các quan sát mâu thuẫn; cần điều tra tiếp.' if status == 'conflicting'
                                      else 'Quan sát phản bác trong phạm vi kiểm tra; không loại trừ trên publisher.' if status == 'contradicted'
                                      else 'Chưa đủ quan sát để đánh giá giả thuyết này.')})
    return cards


def normalize_finish(raw, evidence):
    """Caller already validated schema, owned IDs, target and selected cause."""
    expected = {(x['hypothesis_id'], x['evidence_id']): x['relation'] for x in allowed_links(evidence)}
    for link in raw.get('evidence_links') or []:
        if link['evidence_id'] not in evidence:
            raise DecisionError('unknown_evidence', repairable=True)
        if expected.get((link['hypothesis_id'], link['evidence_id'])) != link['relation']:
            raise DecisionError('invalid_evidence_relation', repairable=True)
    cards = build_hypotheses(evidence)
    code = raw.get('cause_code', 'none')
    selected = next((h for h in cards if h['hypothesis_id'] == code), None)
    usable = [ref for ref in raw.get('evidence_ids', []) if evidence[ref].get('status') != 'unavailable']
    # This label describes scoped support, never proof of KPI causality.
    assessment = ('supported_hypothesis' if selected and selected['status'] == 'supported'
                  else 'ambiguous' if usable else 'insufficient_evidence')
    scope = selected['claim_scope'] if selected else 'unknown'
    summary = (f"{selected['label']}: {selected['explanation']}" if selected
               else 'L1 ghi nhận bất thường; chưa chốt nguyên nhân từ bằng chứng hiện có.')
    limits = [SCOPE_LIMITS[scope], 'Các giả thuyết độc lập: phản bác một giả thuyết không phản bác giả thuyết khác.']
    missing = [h['label'] for h in cards if h['status'] == 'unknown']
    if missing:
        limits.append('Chưa đủ bằng chứng: ' + ', '.join(missing) + '.')
    return {**raw, 'relationship_version': VERSION, 'hypotheses': cards,
            'evidence_links': allowed_links(evidence), 'assessment': assessment,
            'cause_status': 'supported_hypothesis' if assessment == 'supported_hypothesis' else 'unresolved' if usable else 'insufficient_evidence',
            'claim_scope': scope, 'summary': summary, 'limitations': limits,
            'evidence_ids': list(dict.fromkeys(usable + (selected['supporting_evidence_ids'] if selected else []))),
            'counter_evidence_ids': selected['contradicting_evidence_ids'] if selected else [],
            'contradictions': [selected['explanation']] if selected and selected['status'] == 'conflicting' else []}
