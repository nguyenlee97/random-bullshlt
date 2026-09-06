"""Real Mongo atomicity/reclaim acceptance, isolated from the live worker queue.

Uses the deployed queue functions with a dedicated real Mongo collection. No
provider calls or OA events; the one QA document is retained for inspection.
"""
import asyncio
from datetime import timedelta
import json
from pathlib import Path
import socket
import subprocess
import sys

sys.path.insert(0, '/var/www/agent-api')
from config import config
from evaluation import investigation_jobs as jobs
from motor.motor_asyncio import AsyncIOMotorClient

COLLECTION = 'evaluation_vps_qa_jobs_20260831'
POLICY = {'enabled': True, 'level': 'L2', 'version': 'vps-qa-isolated'}
INCIDENT = {'incident_id': 'INC-MONGOQA', 'campaign_id': 'EVAL-QA-MONGO-20260831',
            'dataset_revision': 1, 'state': 'open'}


async def main():
    assert socket.gethostname() == 'momolita'
    db_client = AsyncIOMotorClient(config.MONGODB_URI)
    col = db_client[config.MONGODB_DB][COLLECTION]
    async def actual_collection():
        return col
    jobs.collection = actual_collection
    try:
        if sys.argv[1] == 'reclaim':
            job = await jobs.claim()
            assert job and job['attempts'] == 2 and job['model_calls'] == 1
            assert job['tasks']['performance']['status'] == 'completed'
            await jobs.checkpoint(job, {'status': 'completed'})
            print('Fresh process reclaimed expired lease with saved budget and tasks')
            return
        assert await col.count_documents({}) == 0, 'QA run already exists; do not overwrite evidence'
        await jobs.ensure_indexes()
        results = await asyncio.gather(*(jobs.enqueue(INCIDENT['campaign_id'], INCIDENT, POLICY) for _ in range(12)))
        assert len({j['job_id'] for j in results}) == 1 and await col.count_documents({}) == 1
        claims = await asyncio.gather(*(jobs.claim() for _ in range(12)))
        assert len([j for j in claims if j]) == 1
        job = next(j for j in claims if j)
        await jobs.checkpoint(job, {'tasks': {'performance': {'status': 'completed'}}}, spend_call=True)
        await col.update_one({'_id': job['job_id']}, {'$set': {'lease_until': jobs.now() - timedelta(seconds=1)}})
        child = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).resolve()), 'reclaim',
                                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(child.communicate(), timeout=20)
        assert child.returncode == 0, stderr.decode()[:300]
        try:
            await jobs.checkpoint(job, {'status': 'corrupted'})
        except RuntimeError:
            pass
        else:
            raise AssertionError('Stale owner was able to write')
        replay = await jobs.enqueue(INCIDENT['campaign_id'], INCIDENT, POLICY)
        assert replay['status'] == 'completed' and replay['model_calls'] == 1
        assert replay['attempts'] == 2 and 'lease_token' not in replay
        print(json.dumps({'storage': 'real Mongo; isolated QA collection',
                          'concurrent_enqueues': 12, 'unique_jobs': 1,
                          'concurrent_claims': 12, 'winning_claims': 1,
                          'fresh_process_reclaim': 'passed', 'stale_owner_write': 'denied',
                          'budget_and_tasks_preserved': True, 'completed_replay': 'passed'}))
    finally:
        db_client.close()


asyncio.run(main())
