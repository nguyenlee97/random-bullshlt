"""Parallel specialist tool loops with a bounded coordinator review.

Only evidence collection is delegated. No agent receives actor tokens, a
campaign mutator, arbitrary URL/SQL tools, or the scenario ground truth.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from time import monotonic

from evaluation.agent_model import decide
from evaluation.decision_contract import DecisionError, ModelResponseError, failure, parse_decision, validated_finish
from evaluation.evidence_tools import EvidenceTools, ROLE_TOOLS, TOOL_DESCRIPTIONS, model_evidence
from evaluation.investigation_jobs import VERSION
from evaluation.evidence_relations import VERSION as RELATION_VERSION, allowed_links, build_hypotheses
from evaluation.investigation_resume import snapshot_signature, restore

MAX_SPECIALIST_TOOLS = 3
MAX_REPAIRS_PER_ROLE = 1
MAX_COORDINATOR_DELEGATIONS = 2
REQUIRED_TOOLS = {
    'performance': ('metrics_window',),
    'creative': ('inspect_render', 'creative_compatibility'),
    'setup': ('config_drift',),
    'placement': ('placement_benchmark',),
}


def initial_roles(issue: str) -> list[str]:
    if issue == 'config_drift':
        return ['performance', 'setup']
    if issue in {'ctr_regression', 'creative_failure', 'click_tracking_failure', 'robust_trend_drop'}:
        return ['performance', 'creative', 'placement']
    if issue in {'delivery_drop', 'pacing_error'}:
        return ['performance', 'placement', 'setup']
    return ['performance']


def _validated_finish(result: dict, evidence: dict) -> dict:
    return validated_finish(result, evidence)


async def orchestrate(job: dict, incident: dict, ctx, fixture, *, progress, guard, model=None, renderer=None) -> dict:
    model = model or decide
    tools = EvidenceTools(ctx, job['dataset_revision'], fixture, renderer=renderer)
    signature = snapshot_signature(job, ctx, fixture)
    tasks, evidence = restore(job, ctx, signature)
    lock = asyncio.Lock()
    prompt_identity = {'issue_type': incident['issue_type'], 'scope': ctx.scope,
                       'dataset_revision': job['dataset_revision'], 'evaluation_dates': ctx.evaluation_dates}

    async def save():
        await progress({'tasks': deepcopy(tasks), 'evidence': deepcopy(evidence), 'snapshot_signature': signature})

    async def ask(role, context, available, image=None):
        await guard()
        # Persist reservation first. Crashed calls consume budget on restart.
        await progress({}, spend_call=True)
        task = tasks[role]
        task.update(phase='model', current_tool=None)
        timing = {'kind': 'model', 'started_at': datetime.now(timezone.utc).isoformat(),
                  'attempt': job.get('attempts', 1), 'status': 'running'}
        task.setdefault('timings', []).append(timing)
        async with lock:
            await save()
        started = monotonic()
        try:
            raw = await asyncio.wait_for(model(role, context, tools=available, image=image), timeout=45)
            result = parse_decision(raw)
            timing['status'] = 'completed'
            return result
        except TimeoutError as exc:
            timing.update(status='failed', error_code='model_timeout')
            raise ModelResponseError('model_timeout') from exc
        except asyncio.CancelledError:
            timing['status'] = 'interrupted'
            raise
        except Exception as exc:
            timing.update(status='failed', **failure(exc))
            raise
        finally:
            timing['duration_ms'] = round((monotonic() - started) * 1000)
            async with lock:
                await save()

    async def checked_decision(role, context, available, collected, task, image=None):
        # One shared protocol/transport retry per role; collected tools are not replayed.
        # 4 roles * (3 tools + 1 synthesis + 1 repair) + coordinator (3 + 1)
        # fits the existing persisted global ceiling of 24 calls on a fresh run.
        correction = None
        while True:
            try:
                payload = {**context, 'tools_already_collected': task['tool_calls'],
                           'allowed_actions': ['finish'] if not available else ['finish', 'delegate' if role == 'coordinator' else 'tool'],
                           'valid_evidence_ids': list(collected),
                           'allowed_evidence_links': allowed_links(collected)}
                if correction:
                    payload['protocol_correction'] = correction
                result = await ask(role, payload, available, image)
                if result['action'] == 'finish':
                    if any(tool not in task['tool_calls'] for tool in REQUIRED_TOOLS.get(role, ())):
                        raise DecisionError('required_evidence', repairable=True)
                    return validated_finish(result, collected, typed=True)
                if not available:
                    raise DecisionError('finish_required', repairable=True)
                expected = 'delegate' if role == 'coordinator' else 'tool'
                if result['action'] != expected:
                    raise DecisionError('invalid_action', repairable=True)
                if result['target'] not in available:
                    allowed = ROLE_TOOLS if role == 'coordinator' else ROLE_TOOLS[role]
                    if result['target'] in allowed:
                        raise DecisionError('duplicate_tool', repairable=True)
                    raise DecisionError('unauthorized_tool')
                return result
            except (DecisionError, ModelResponseError) as exc:
                retryable = (exc.repairable if isinstance(exc, DecisionError)
                             else exc.code in {'model_timeout', 'model_unavailable', 'model_incomplete'})
                repair = retryable and task.get('repairs_used', 0) < MAX_REPAIRS_PER_ROLE
                task.setdefault('validation_errors', []).append({
                    'code': exc.code, 'repair_requested': repair,
                    'kind': 'protocol' if isinstance(exc, DecisionError) else 'provider',
                    'phase': 'finish' if not available else 'collect',
                    'attempt': job.get('attempts', 1),
                    'at': datetime.now(timezone.utc).isoformat(),
                })
                if repair:
                    task['repairs_used'] = task.get('repairs_used', 0) + 1
                async with lock:
                    await save()
                if not repair:
                    raise
                # Do not reflect invalid IDs, provider payloads or exception text.
                correction = {'code': exc.code, 'instruction': str(exc),
                              'remaining_repairs': 0, 'valid_evidence_ids': list(collected)}

    async def specialist(role):
        if tasks.get(role, {}).get('status') == 'completed':
            tasks[role]['reused_evidence_count'] = len(tasks[role].get('tool_evidence_ids', {}))
            tasks[role]['phase'] = 'reused'
            return
        previous = tasks.get(role, {})
        task = {**previous, 'role': role, 'status': 'running', 'phase': 'starting',
                'started_at': datetime.now(timezone.utc).isoformat(),
                'tool_calls': previous.get('tool_calls', []), 'tool_evidence_ids': previous.get('tool_evidence_ids', {}),
                'result': None, 'repairs_used': 0, 'validation_errors': previous.get('validation_errors', []),
                'reused_evidence_count': len(previous.get('tool_evidence_ids', {}))}
        for key in ('error', 'error_code', 'completed_at'):
            task.pop(key, None)
        tasks[role] = task
        async with lock:
            await save()
        collected = {ref: evidence[ref] for ref in task['tool_evidence_ids'].values()}

        async def collect(tool_name):
            await guard()
            task.update(phase='tool', current_tool=tool_name, pending_tool=tool_name)
            timing = {'kind': 'tool', 'tool': tool_name, 'status': 'running',
                      'attempt': job.get('attempts', 1), 'started_at': datetime.now(timezone.utc).isoformat()}
            task.setdefault('timings', []).append(timing)
            async with lock:
                await save()
            started = monotonic()
            try:
                item = await asyncio.wait_for(tools.execute(role, tool_name), timeout=25)
                timing['status'] = 'unavailable' if item.get('status') == 'unavailable' else 'completed'
            except (PermissionError, asyncio.CancelledError):
                timing['status'] = 'interrupted'
                raise
            except Exception as exc:
                code = 'tool_timeout' if isinstance(exc, TimeoutError) else 'tool_failed'
                timing.update(status='failed', error_code=code)
                item = {'evidence_id': f"EVD-{role}-{tool_name}-unavailable", 'probe_id': tool_name,
                        'status': 'unavailable', 'source': 'tool_error', 'error_code': code,
                        'summary': 'Read-only evidence unavailable; not evidence of a healthy system.',
                        'campaign_id': ctx.campaign_id, 'scope': ctx.scope, 'tool_version': 'readonly-v1',
                        'dataset_revision': job['dataset_revision'], 'observed_at': datetime.now(timezone.utc).isoformat()}
            finally:
                timing['duration_ms'] = round((monotonic() - started) * 1000)
                async with lock:
                    await save()
            collected[item['evidence_id']] = item
            task['tool_calls'].append(tool_name)
            task['tool_evidence_ids'][tool_name] = item['evidence_id']
            task.pop('pending_tool', None)
            task['current_tool'] = None
            async with lock:
                evidence[item['evidence_id']] = item
                await save()

        try:
            if task.get('pending_tool') and len(task['tool_calls']) < MAX_SPECIALIST_TOOLS:
                await collect(task['pending_tool'])
            for _ in range(MAX_SPECIALIST_TOOLS + 1):
                step = len(task['tool_calls'])
                required = [tool for tool in REQUIRED_TOOLS.get(role, ()) if tool not in task['tool_calls']]
                available = {t: TOOL_DESCRIPTIONS[t] for t in ROLE_TOOLS[role]
                             if t not in task['tool_calls']} if step < MAX_SPECIALIST_TOOLS else {}
                if required and MAX_SPECIALIST_TOOLS - step <= len(required):
                    available = {tool: available[tool] for tool in required if tool in available}
                screenshot = next((e.get('screenshot_base64') for e in collected.values() if e.get('screenshot_base64')), None)
                result = await checked_decision(role, {**prompt_identity,
                    'evidence': [model_evidence(e) for e in collected.values()],
                    'remaining_tool_calls': MAX_SPECIALIST_TOOLS - step,
                    'required_tools_remaining': required,
                    'instruction': 'Collect relevant evidence then finish. Reserve your conclusion; do not confuse symptom with cause.'
                        if available else 'Collection finished. You MUST finish now using collected evidence and explicit limitations.'},
                    available, collected, task, screenshot)
                if result['action'] == 'finish':
                    # A specialist may cite only evidence it actually received.
                    task['result'] = result
                    task['status'] = 'partial' if not collected or any(
                        e.get('status') == 'unavailable' for e in collected.values()) else 'completed'
                    break
                await collect(result['target'])
        except asyncio.CancelledError:
            task['status'] = 'interrupted'
            raise
        except Exception as exc:
            task.update(status='failed', **failure(exc))
        finally:
            task.update(phase=task['status'], current_tool=None)
            task['completed_at'] = datetime.now(timezone.utc).isoformat()
            async with lock:
                await save()

    async def batch(roles):
        children = [asyncio.create_task(specialist(role)) for role in roles]
        try:
            await asyncio.gather(*children)
        finally:
            for child in children:
                if not child.done():
                    child.cancel()
            await asyncio.gather(*children, return_exceptions=True)

    # Reclaim all interrupted/partial delegated specialists as well as the
    # initial pair; merely retaining their old task would make retries inert.
    resume_roles = [role for role in ROLE_TOOLS if role in tasks and tasks[role].get('status') != 'completed']
    await batch(list(dict.fromkeys(initial_roles(incident['issue_type']) + resume_roles)))
    review = None
    tasks['coordinator'] = {'role': 'coordinator', 'status': 'running', 'phase': 'review', 'tool_calls': [],
                            'repairs_used': 0, 'validation_errors': [],
                            'started_at': datetime.now(timezone.utc).isoformat()}
    await save()
    # Coordinator can commission up to two additional specialists then finish.
    for step in range(MAX_COORDINATOR_DELEGATIONS + 1):
        remaining = {role: 'Delegate a bounded read-only investigation' for role in ROLE_TOOLS if role not in tasks}
        if step == MAX_COORDINATOR_DELEGATIONS:
            remaining = {}
        try:
            result = await checked_decision('coordinator', {**prompt_identity, 'tasks': tasks,
                'evidence': [model_evidence(e) for e in evidence.values()],
                'instruction': 'Check competing explanations and limitations. Delegate only if evidence is missing. '
                    'Otherwise finish. CTR drop is a symptom, not a causal hypothesis.'}, remaining, evidence, tasks['coordinator'])
            if result['action'] == 'delegate' and result['target'] in remaining:
                tasks['coordinator']['tool_calls'].append('delegate_' + result['target'])
                await save()
                await batch([result['target']])
                continue
            review = result
            break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            tasks['coordinator'].update(**failure(exc))
            break
    review_succeeded = review is not None
    if review is None:
        review = {'assessment': 'insufficient_evidence', 'summary': 'Coordinator chưa hoàn tất kiểm tra bằng chứng.',
                  'evidence_ids': [], 'contradictions': [], 'cause_code': 'none', 'cause_status': 'insufficient_evidence',
                  'claim_scope': 'unknown', 'limitations': ['Chưa có kết luận coordinator đã kiểm tra.']}
    tasks['coordinator'].update(status='completed' if review_succeeded else 'failed')
    # A missing review remains a partial run even when every specialist finished.
    partial = any(t['status'] != 'completed' for t in tasks.values())
    if partial and review['assessment'] == 'supported_hypothesis':
        review['assessment'] = 'ambiguous'
        review['cause_status'] = 'unresolved'
    if partial:
        review['limitations'] = ['Một hoặc nhiều specialist chưa hoàn tất; chưa chốt nguyên nhân.'] + review.get('limitations', [])
    await guard()
    tasks['coordinator'].update(result=review, completed_at=datetime.now(timezone.utc).isoformat())
    tasks['coordinator']['phase'] = tasks['coordinator']['status']
    bundle = {'bundle_id': job['job_id'] + '-a' + str(job.get('attempts', 1)),
              'job_id': job['job_id'], 'bundle_version': VERSION, 'mode': 'multi_agent',
              'snapshot_signature': signature,
              'model': job.get('model'), 'provider': job.get('provider'),
              'incident_id': incident['incident_id'], 'campaign_id': ctx.campaign_id, 'scope': ctx.scope,
              'issue_type': incident['issue_type'], 'dataset_revision': job['dataset_revision'],
              'policy_version': job['policy_version'], 'trigger': job['trigger'],
              'created_at': datetime.now(timezone.utc).isoformat(), 'supported': True,
              'assessment': review['assessment'], 'ambiguous': review['assessment'] == 'ambiguous',
              'symptom_status': 'detected_by_l1', 'cause_status': review['cause_status'],
              'cause_code': review['cause_code'], 'claim_scope': review['claim_scope'], 'limitations': review['limitations'],
              'summary': review['summary'], 'review': review, 'tasks': tasks,
              'probes': list(evidence.values()), 'hypotheses': build_hypotheses(evidence), 'top_hypothesis': None,
              'relationship_version': RELATION_VERSION, 'evidence_links': allowed_links(evidence),
              'completion': {'completed_roles': sum(t['status'] == 'completed' for t in tasks.values()),
                             'total_roles': len(tasks), 'unavailable_probes': sum(e.get('status') == 'unavailable' for e in evidence.values()),
                             'reused_evidence': sum(t.get('reused_evidence_count', 0) for t in tasks.values())},
              'score_semantics': 'evidence_referenced_not_causal_probability',
              'recovery_options': [], 'mutations': [], 'partial': partial}
    await progress({'tasks': tasks, 'evidence': evidence, 'review': review})
    return bundle
