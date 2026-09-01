"""Bounded real-model counterfactual suite on the verified staging VPS.

Uses the deployed orchestrator and Scenario Lab DOM builder, synthetic matching
metadata and identical measurements. No campaign/Mongo/OA/publisher mutations.
Case labels/expected answers never enter model context. Persistent run marker
prevents an accidental rerun after interruption. This is not a full HTTP test.
"""
import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import re
import socket
import subprocess
import sys

sys.path.insert(0, '/var/www/agent-api')
from evaluation.evidence_tools import EvidenceTools
from evaluation.multi_agent import orchestrate
from evaluation.probes import InvestigationContext
from evaluation.investigation_jobs import VERSION, MAX_MODEL_CALLS
from evaluation.evidence_relations import VERSION as RELATION_VERSION
from config import config


async def main():
    assert socket.gethostname() == 'momolita'
    parser=argparse.ArgumentParser()
    parser.add_argument('--release', required=True)
    parser.add_argument('--run-id', default='initial')
    parser.add_argument('--repetitions', type=int, choices=[1,2], default=2)
    args=parser.parse_args()
    assert re.fullmatch(r'202[6-9][0-9]{4}-evaluation-m[0-9]+-[0-9]+',args.release)
    assert re.fullmatch(r'[a-z0-9-]{1,40}',args.run_id)
    root=Path('/var/backups/advertising-agent/evaluation')/args.release
    assert root.is_dir()
    output=root/('model-suite-'+args.run_id+'.json')
    assert not output.exists(), 'Run already exists; do not repeat provider calls'
    journal={'engine_version':VERSION,'model':config.EVALUATION_AGENT_MODEL,
             'repetitions':args.repetitions,'max_calls_per_case':MAX_MODEL_CALLS,'cases':{}}
    def save():
        output.write_text(json.dumps(journal,ensure_ascii=False,indent=2)); output.chmod(0o600)
    save()
    script="const {buildRuntimeFixture:f}=require('./lib/investigationFixtures'); console.log(JSON.stringify(['click_overlay','healthy_baseline'].map(presetId=>f({presetId,targetPlacementId:'QA_SLOT'},['QA_SLOT']))))"
    blocked,clear=json.loads(subprocess.check_output(['node','-e',script],cwd='/var/www/backend'))
    baseline=[{'placementId':'QA_SLOT','date':'2026-08-'+str(day),'impressions':10000,
               'clicks':100,'spend':100000,'reach':5000,'conversions':5} for day in range(22,32)]
    active=deepcopy(baseline)
    for row in active[-2:]: row['clicks']=0
    base=InvestigationContext(campaign_id='QA-MODEL-PAIR',scope='QA_SLOT',issue_type='ctr_regression',
        baseline_records=baseline,active_records=active,
        order={'creatives':[{'size':'600x180','format':'banner','zones':['QA_SLOT']}]},
        zone_map={'QA_SLOT':{'size':'600x180','format':'banner'}},
        evaluation_dates=['2026-08-30','2026-08-31'])
    # Expectations are used by the grader only, never in prompt_identity/context.
    cases=[('overlay',blocked,'600x180','click_obstruction','isolated_document'),
           ('clear',clear,'600x180','none','unknown'),
           ('unavailable',None,'600x180','none','unknown'),
           ('metadata',clear,'300x250','creative_contract_mismatch','creative_metadata')]
    concurrency=asyncio.Semaphore(2)
    async def run(case, repetition):
        label,fixture,size,expected_cause,expected_scope=case
        key=f'{label}-{repetition}'
        async with concurrency:
            ctx=deepcopy(base); ctx.order['creatives'][0]['size']=size
            job={'job_id':'QA-PAIR','campaign_id':ctx.campaign_id,'incident_id':'INC-QAPAIR',
                 'dataset_revision':2,'policy_version':'qa-pair','trigger':'test',
                 'tasks':{},'evidence':{},'model_calls':0,'attempts':1}
            row={'status':'running','model_calls':0}; journal['cases'][key]=row; save()
            async def guard(): return None
            async def progress(changes, *, spend_call=False):
                if spend_call:
                    if job['model_calls']>=MAX_MODEL_CALLS: raise RuntimeError('QA model budget exhausted')
                    job['model_calls']+=1
                job.update(deepcopy(changes)); row['model_calls']=job['model_calls']; save()
            try:
                observation=await EvidenceTools(ctx,2,fixture).execute('creative','inspect_render')
                bundle=await asyncio.wait_for(orchestrate(job,
                    {'incident_id':'INC-QAPAIR','issue_type':'ctr_regression'},ctx,fixture,
                    progress=progress,guard=guard),timeout=240)
                # Explicit limits and selected evidence required, not just expected words.
                cause_ok=bundle.get('cause_code')==expected_cause and bundle.get('claim_scope')==expected_scope
                render_collected=any(p['probe_id']=='inspect_render' for p in bundle['probes'])
                assessment_ok=(bundle['assessment']=='supported_hypothesis' if expected_cause!='none'
                               else bundle['assessment']!='supported_hypothesis')
                complete_ok=not bundle['partial'] if label!='unavailable' else bundle['partial']
                checks={'cause_and_scope':cause_ok,'assessment':assessment_ok,'completeness':complete_ok,
                        'limitations':bool(bundle.get('limitations')),'independent_render_collected':render_collected}
                # Separate safe uncertainty, diagnostic classification and role
                # execution. An unavailable fixture does not excuse a timeout.
                checks['role_execution'] = all(t.get('status') in {'completed', 'partial'} and t.get('result')
                                               for t in bundle['tasks'].values())
                cards = {h['hypothesis_id']: h for h in bundle.get('hypotheses', [])}
                checks['typed_relations'] = bundle.get('relationship_version') == RELATION_VERSION and bool(cards)
                if label == 'metadata':
                    checks['independent_hypotheses'] = (cards.get('click_obstruction', {}).get('status') == 'contradicted'
                        and cards.get('creative_contract_mismatch', {}).get('status') == 'supported')
                row.update(status='completed',checks=checks,gate_passed=all(checks.values()),bundle=bundle,
                           observation={k:v for k,v in observation.items() if k!='screenshot_base64'})
                print(json.dumps({'case':key,'calls':job['model_calls'],'gate_passed':row['gate_passed'],
                    'checks':checks,'cause':bundle.get('cause_code'),'scope':bundle.get('claim_scope'),
                    'assessment':bundle['assessment'],'partial':bundle['partial'],'summary':bundle['summary'],
                    'tasks':{k:{f:t.get(f) for f in ['status','tool_calls','error_code','validation_errors']} for k,t in bundle['tasks'].items()}},ensure_ascii=False),flush=True)
            except Exception as exc:
                row.update(status='failed',gate_passed=False,error_type=type(exc).__name__)
                print(json.dumps({'case':key,'status':'failed','error_type':type(exc).__name__}),flush=True)
            finally: save()
    await asyncio.gather(*(run(case,rep) for rep in range(1,args.repetitions+1) for case in cases))
    journal['passed']=sum(bool(r.get('gate_passed')) for r in journal['cases'].values())
    journal['total']=len(journal['cases']); journal['calls']=sum(r['model_calls'] for r in journal['cases'].values())
    journal['quality_dimensions'] = {
        'diagnostic_passed': sum(bool(r.get('checks', {}).get('cause_and_scope') and r.get('checks', {}).get('assessment')) for r in journal['cases'].values()),
        'execution_passed': sum(bool(r.get('checks', {}).get('role_execution')) for r in journal['cases'].values()),
        'evidence_contract_passed': sum(bool(r.get('checks', {}).get('typed_relations') and r.get('checks', {}).get('limitations') and r.get('checks', {}).get('independent_render_collected')) for r in journal['cases'].values()),
    }
    save()
    print(json.dumps({k:journal[k] for k in ['engine_version','model','passed','total','calls','quality_dimensions']}),flush=True)
    if journal['passed']!=journal['total']: raise SystemExit(1)


asyncio.run(main())
