"""Release-4 public HTTP acceptance using the existing isolated QA account.

Only one explicit incident investigation, one Q&A request and replays. No
scenario apply/order mutation/OA send. Credentials stay in the old server file.
Run start, poll, finish separately; no long blocking polling loop.
"""
import json
from pathlib import Path
import socket
import sys
import uuid
import re
import hashlib

sys.path.insert(0, '/tmp')
from evaluation_vps_smoke import ARTIFACT, CAMPAIGN, BASE, agent_db, client, call
from config import config
from evaluation.investigation_jobs import VERSION
from evaluation.evidence_relations import VERSION as RELATION_VERSION

OUTPUT = Path('/var/backups/advertising-agent/evaluation/20260831-evaluation-m2-4/http-stability.json')


def save(value):
    OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2)); OUTPUT.chmod(0o600)


def main():
    global OUTPUT
    assert socket.gethostname() == 'momolita'
    mode = sys.argv[1]
    if len(sys.argv) > 2:
        release = sys.argv[2]
        assert re.fullmatch(r'202[6-9][0-9]{4}-evaluation-m[0-9]+-[0-9]+', release)
        OUTPUT = OUTPUT.parent.parent / release / 'http-stability.json'
    state = json.loads(ARTIFACT.read_text())
    assert not config.EVALUATION_WORKER_ENABLED
    assert agent_db()['zalo_threads'].count_documents({'user_id': state['user_id']}) == 0
    prefix = f'/evaluation/campaigns/{CAMPAIGN}'
    with client(state) as c:
        if mode == 'start':
            assert not OUTPUT.exists(), 'Already started; use poll/finish'
            current = call(c, 'GET', prefix)
            incident = next(i for i in current['incidents'] if i['incident_id'] == 'INC-239833')
            assert incident['dataset_revision'] == 2
            result = {'incident_id': incident['incident_id'], 'status': 'starting'}
            save(result)
            try:
                call(c, 'PUT', prefix+'/policy', {'enabled': True, 'level': 'L2'})
                path = prefix+'/incidents/'+incident['incident_id']+'/actions'
                response = call(c, 'POST', path, {'action': 'investigate'}, expected=202)
                job = response['investigation_job']
                assert job['engine_version'] == VERSION
                result.update(job_id=job['job_id'], status=job['status'])
                save(result)
                print(json.dumps(result))
            except Exception:
                call(c, 'PUT', prefix+'/policy', {'enabled': False})
                raise
            return
        result = json.loads(OUTPUT.read_text())
        if mode == 'retry-finish':
            request = result['question_request']
            key = 'IQ-' + hashlib.sha256(f"web|{CAMPAIGN}|{result['incident_id']}|{request['requestId']}".encode()).hexdigest()
            previous = agent_db()['evaluation_incident_questions'].find_one({'_id': key}) or {}
            assert previous.get('status') == 'failed' and previous.get('attempts') == 1, 'Only one explicit same-request retry'
            result['first_question_attempt'] = {k: previous.get(k) for k in ['status', 'attempts', 'error_type']}
            save(result)
            call(c, 'PUT', prefix+'/policy', {'enabled': True, 'level': 'L2'})
            try:
                sys.argv[1] = 'finish'
                main()
            finally:
                call(c, 'PUT', prefix+'/policy', {'enabled': False})
            return
        if mode == 'disable':
            call(c, 'PUT', prefix+'/policy', {'enabled': False})
            print('QA policy disabled'); return
        current = call(c, 'GET', prefix)
        job = next(j for j in current['investigation_jobs'] if j['job_id'] == result['job_id'])
        summary = {k: job.get(k) for k in ['job_id','status','attempts','model_calls','error','notification_enqueue_count']}
        summary['tasks'] = {role:{k:t.get(k) for k in ['status','error_code','validation_errors']} for role,t in job['tasks'].items()}
        if mode == 'poll':
            request = result.get('question_request')
            if request:
                key = 'IQ-' + hashlib.sha256(f"web|{CAMPAIGN}|{result['incident_id']}|{request['requestId']}".encode()).hexdigest()
                question = agent_db()['evaluation_incident_questions'].find_one({'_id': key}) or {}
                summary['question'] = {k: question.get(k) for k in ['status', 'attempts', 'error_type']}
            print(json.dumps(summary, ensure_ascii=False)); return
        assert mode == 'finish'
        assert job['status'] not in {'queued', 'running'}, 'Not finished; use poll'
        try:
            assert job['status'] == 'completed', 'Investigation did not complete'
            incident = next(i for i in current['incidents'] if i['incident_id'] == result['incident_id'])
            bundle = incident['investigation']
            assert bundle['job_id'] == result['job_id'] and bundle['bundle_version'] == VERSION
            assert bundle.get('snapshot_signature') and bundle.get('relationship_version') == RELATION_VERSION
            assert bundle['limitations'] and not bundle['mutations']
            path = prefix+'/incidents/'+result['incident_id']
            replay = call(c, 'POST', path+'/actions', {'action': 'investigate'}, expected=202)['investigation_job']
            assert replay['job_id'] == job['job_id'] and replay['model_calls'] == job['model_calls']
            body = result.setdefault('question_request', {
                'question': 'Các bằng chứng hiện có nói được gì về vùng click, và điều gì vẫn chưa được chứng minh trên publisher?',
                'requestId': 'qa-stability-'+uuid.uuid4().hex, 'expectedRevision': 2,
                'expectedBundleId': bundle['bundle_id']})
            save(result)
            answer = call(c, 'POST', path+'/questions', body)
            assert call(c, 'POST', path+'/questions', body) == answer
            for action in ['prepare_recovery','start_recovery','verify','resolve']:
                call(c, 'POST', path+'/actions', {'action': action}, expected=409)
            assert job.get('notification_enqueue_count') == 0
            rows = c.get('https://api.pawgrammers.io.vn/api/reports/data/'+CAMPAIGN).json()
            analytics = c.get('https://api.pawgrammers.io.vn/api/analytics/data', params={'campaignId': CAMPAIGN}).json()
            analyses = c.get('https://api.pawgrammers.io.vn/api/reports/analysis/'+CAMPAIGN).json()
            assert len(rows) == len(analytics) == 20 and len(analyses) == 6
            assert len({row['inputHash'] for row in rows+analytics+analyses}) == 1
            assert sum(row['clicks'] for row in rows) == 700
            result.update(status='passed', job=summary,
                          investigation={k:bundle.get(k) for k in ['cause_code','claim_scope','assessment','limitations','summary']},
                          completion=bundle.get('completion'), hypotheses=bundle.get('hypotheses'),
                          answer=answer, report_consistency=True, l3_blocked=True, replay_no_extra_calls=True)
            save(result)
            print(json.dumps(result, ensure_ascii=False))
        except Exception as exc:
            result.update(status='failed', error_type=type(exc).__name__)
            save(result)
            raise
        finally:
            call(c, 'PUT', prefix+'/policy', {'enabled': False})
            print('QA policy disabled; global scheduler remains off')


if __name__ == '__main__': main()
