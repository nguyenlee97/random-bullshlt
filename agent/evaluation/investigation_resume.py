"""Reuse read-only observations only within the exact input snapshot."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json

from evaluation.evidence_tools import clean_context, ROLE_TOOLS
from evaluation.investigation_jobs import VERSION
from evaluation.engine import DEFAULT_POLICY


def snapshot_signature(job, ctx, fixture):
    context = asdict(clean_context(ctx))
    # Scheduler timestamps and leases are not evidence or policy semantics.
    # Re-saving an identical policy must not invalidate an otherwise valid Q&A.
    context['policy'] = {key: ctx.policy.get(key, default) for key, default in DEFAULT_POLICY.items() if key != 'version'}
    payload = [VERSION, job.get('model'), job.get('provider'), job['policy_version'],
               job['dataset_revision'], context, fixture]
    # Persist only the digest, never this input or credentials in progress logs.
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def restore(job, ctx, signature):
    previous = deepcopy(job.get('tasks') or {})
    if job.get('snapshot_signature') != signature:
        # Retain delegated role selection, not observations from a stale context.
        return {role: {'role': role, 'status': 'interrupted', 'tool_calls': []}
                for role in previous if role in ROLE_TOOLS}, {}
    evidence = {ref: deepcopy(item) for ref, item in (job.get('evidence') or {}).items()
                if item.get('evidence_id') == ref and item.get('campaign_id') == ctx.campaign_id
                and item.get('scope') == ctx.scope and item.get('dataset_revision') == job['dataset_revision']
                and item.get('tool_version') == 'readonly-v1' and item.get('source') != 'tool_error'}
    tasks, retained = {}, {}
    for role, task in previous.items():
        if role not in ROLE_TOOLS:
            continue
        mapping = {tool: ref for tool, ref in (task.get('tool_evidence_ids') or {}).items()
                   if tool in ROLE_TOOLS[role] and ref in evidence and evidence[ref].get('probe_id') == tool}
        if len(mapping) != len(task.get('tool_calls', [])) or not mapping:
            task.update(status='interrupted', result=None)
        task['tool_evidence_ids'] = mapping
        task['tool_calls'] = list(mapping)
        # A pending read-only tool may be replayed after a worker crash; its
        # model decision has already consumed a durable call reservation.
        if task.get('pending_tool') not in ROLE_TOOLS[role] or task.get('pending_tool') in mapping:
            task.pop('pending_tool', None)
        tasks[role] = task
        retained.update({ref: evidence[ref] for ref in mapping.values()})
    return tasks, retained
