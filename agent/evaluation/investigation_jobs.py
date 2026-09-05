"""Mongo-backed isolated L2 queue. No in-memory durability illusion in production."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import uuid

from config import config

VERSION = 'multi-agent-v7'
ACTIVE = {'queued', 'running'}
MAX_ATTEMPTS = 3
MAX_MODEL_CALLS = 24  # persisted BEFORE a call, includes crash/restart attempts
LEASE_SECONDS = 120


def now():
    return datetime.now(timezone.utc)


async def collection():
    from session import _ensure_mongo
    if not await _ensure_mongo():
        raise RuntimeError('Durable L2 requires MongoDB; investigation was not queued')
    import session
    return session._client[config.MONGODB_DB]['evaluation_investigation_jobs']


def public(doc):
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in doc.items()
            if k not in {'_id', 'lease_token', 'lease_until'}}


async def ensure_indexes():
    col = await collection()
    await col.create_index([('campaign_id', 1), ('created_at', -1)])
    await col.create_index([('status', 1), ('lease_until', 1)])


async def enqueue(campaign_id: str, incident: dict, policy: dict, *, trigger='manual') -> dict:
    if not config.EVALUATION_MULTI_AGENT_ENABLED or not config.OPENAI_API_KEY:
        raise RuntimeError('Multi-agent investigation is disabled or its model key is missing')
    if not policy.get('enabled') or policy.get('level') not in {'L2', 'L3'}:
        raise PermissionError('Enabled L2/L3 policy required')
    if incident.get('campaign_id') != campaign_id:
        raise PermissionError('Incident campaign mismatch')
    if incident.get('state') in {'resolved', 'dismissed', 'false_positive', 'expired'}:
        raise ValueError('Incident is closed')
    revision = incident['dataset_revision']
    identity = f"{VERSION}|{config.EVALUATION_AGENT_MODEL}|{campaign_id}|{incident['incident_id']}|{revision}|{policy['version']}"
    job_id = 'IVR-' + hashlib.sha256(identity.encode()).hexdigest()[:24]
    col = await collection()
    doc = {'job_id': job_id, 'campaign_id': campaign_id, 'incident_id': incident['incident_id'],
           'dataset_revision': revision, 'policy_version': policy['version'], 'engine_version': VERSION,
           'provider': 'openai', 'model': config.EVALUATION_AGENT_MODEL,
           'status': 'queued', 'trigger': trigger, 'created_at': now(), 'updated_at': now(),
           'next_attempt_at': now(),
           'attempts': 0, 'model_calls': 0, 'tasks': {}, 'evidence': {}, 'review': None}
    # _id is the dedup key; no read-before-write race or index startup dependency.
    from pymongo.errors import DuplicateKeyError
    try:
        await col.update_one({'_id': job_id}, {'$setOnInsert': doc}, upsert=True)
    except DuplicateKeyError:
        pass
    # Explicit retries do not reset budget or erase prior evidence/tasks.
    await col.update_one({'_id': job_id, 'status': 'failed', 'attempts': {'$lt': MAX_ATTEMPTS},
                          'model_calls': {'$lt': MAX_MODEL_CALLS}},
                         {'$set': {'status': 'queued', 'updated_at': now(), 'next_attempt_at': now()}})
    if trigger in {'manual', 'zalo'}:
        await col.update_one({'_id': job_id, 'status': {'$in': ['partial', 'stale']}, 'attempts': {'$lt': MAX_ATTEMPTS},
                              'model_calls': {'$lt': MAX_MODEL_CALLS}},
                             {'$set': {'status': 'queued', 'updated_at': now(), 'next_attempt_at': now()},
                              '$unset': {'bundle': '', 'review': ''}})
    return public(await col.find_one({'_id': job_id}))


async def list_jobs(campaign_id: str) -> list[dict]:
    col = await collection()
    # Large screenshots stay in detail/history, not repeated in every poll.
    docs = await col.find({'campaign_id': campaign_id}, {'evidence': 0, 'bundle': 0}).sort('created_at', -1).limit(30).to_list(None)
    return [public(doc) for doc in docs]


async def get_job(campaign_id: str, job_id: str) -> dict | None:
    col = await collection()
    doc = await col.find_one({'_id': job_id, 'campaign_id': campaign_id})
    return public(doc) if doc else None


async def claim() -> dict | None:
    col = await collection()
    stamp = now()
    await col.update_many({'status': 'running', 'lease_until': {'$lte': stamp},
                           'attempts': {'$gte': MAX_ATTEMPTS}},
                          {'$set': {'status': 'failed', 'error': 'Worker retry limit reached', 'updated_at': stamp}})
    return await col.find_one_and_update(
        {'attempts': {'$lt': MAX_ATTEMPTS}, 'next_attempt_at': {'$lte': stamp}, '$or': [
            {'status': 'queued'}, {'status': 'running', 'lease_until': {'$lte': stamp}}]},
        {'$set': {'status': 'running', 'lease_token': uuid.uuid4().hex,
                  'lease_until': stamp + timedelta(seconds=LEASE_SECONDS), 'updated_at': stamp},
         '$inc': {'attempts': 1}}, sort=[('created_at', 1)], return_document=True)


async def checkpoint(job: dict, changes: dict | None = None, *, spend_call=False) -> None:
    col = await collection()
    stamp = now()
    query = {'_id': job['job_id'], 'status': 'running', 'lease_token': job['lease_token'],
             'lease_until': {'$gt': stamp}}
    if spend_call:
        query['model_calls'] = {'$lt': MAX_MODEL_CALLS}
    update = {'$set': {**(changes or {}), 'updated_at': stamp,
                       'lease_until': stamp + timedelta(seconds=LEASE_SECONDS)}}
    if spend_call:
        update['$inc'] = {'model_calls': 1}
    doc = await col.find_one_and_update(query, update, return_document=True)
    if not doc:
        raise RuntimeError('Investigation lease or model budget exhausted')
    job['model_calls'] = doc['model_calls']
