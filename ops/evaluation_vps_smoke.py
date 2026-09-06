"""Explicitly scoped VPS acceptance test; never sends OA or changes existing campaigns.

Run with the deployed Agent venv from /var/www/agent-api. Test credentials stay
in a root-only server artifact. Uses real HTTP auth, Mongo, report service/model,
L1, background L2 and Q&A. No model/DB mocks.
"""
import asyncio
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import uuid

sys.path.insert(0, '/var/www/agent-api')
import httpx
from config import config
from pymongo import MongoClient

BASE = 'https://agent.pawgrammers.io.vn/agent/api/agent'
CAMPAIGN = 'EVAL-QA-20260831-M2'
ARTIFACT = Path('/var/backups/advertising-agent/evaluation/20260831-evaluation-m2-2/smoke-private.json')


def save(state):
    ARTIFACT.write_text(json.dumps(state,ensure_ascii=False,indent=2)); ARTIFACT.chmod(0o600)


def client(state):
    c = httpx.Client(timeout=170)
    for key,value in state.get('cookies',{}).items(): c.cookies.set(key,value,domain='agent.pawgrammers.io.vn',path='/')
    return c


def call(c, method, path, body=None, expected=200, csrf=True):
    headers = {'X-CSRF-Token':c.cookies.get('aa_csrf')} if csrf and c.cookies.get('aa_csrf') else {}
    r = c.request(method,BASE+path,json=body,headers=headers)
    if r.status_code != expected:
        raise RuntimeError(f'{method} {path}: {r.status_code}: {r.text[:450]}')
    return r.json()


def agent_db():
    return MongoClient(config.MONGODB_URI,serverSelectionTimeoutMS=5000)[config.MONGODB_DB]


def seed_reports(state):
    script = r'''
require('dotenv').config();const mongoose=require('mongoose');
const {normalizeReportInput}=require('./lib/reportMeasurement');
const Campaign=require('./models/Campaign'), Analytics=require('./models/AnalyticsRecord');
const gen=require('./services/reportGenerator');
const id='EVAL-QA-20260831-M2';
(async()=>{
await mongoose.connect(process.env.MONGODB_URI);
if(await Campaign.exists({orderId:id}))throw Error('Test campaign already exists');
const zones=['ZingNews_Masthead','BaoMoi_Masthead'];
const order={orderId:id,brand:'[EVAL QA 20260831] Click overlay',objective:'awareness',status:'paused',
budget:10000000,startDate:'2026-08-22',endDate:'2026-08-31',placements:zones,
creatives:[{name:'QA isolated document',format:'banner',size:'600x180',zones}]};
await Campaign.create(order);
const input=normalizeReportInput({...order,campaignId:id,zones,creative:{files:order.creatives}});
const rows=[];for(const placementId of zones)for(let day=22;day<=31;day++)rows.push({
campaignId:id,inputHash:input.inputHash,placementId,date:'2026-08-'+day,
channel:'news',format:'banner',impressions:5000,clicks:50,spend:500000,reach:3000,
conversions:10,vi:62,ctr:1,outcomes:{visits:40}});
await Analytics.insertMany(rows);await gen.generateReports(input);
const status=await gen.getReportStatus(id);if(status.ready!==6)throw Error('Baseline reports not ready');
console.log('QA_BASELINE_READY',JSON.stringify(status));await mongoose.disconnect();
})().catch(e=>{console.error(e.name+': '+e.message);process.exit(1)});
'''
    env = dict(os.environ)
    processes = json.loads(subprocess.check_output(['pm2','jlist']))
    runtime = next(p['pm2_env'] for p in processes if p['name']=='adspilot-api')
    for key in ('OPENAI_API_KEY','MONGODB_URI'):
        if runtime.get(key): env[key] = runtime[key]
    subprocess.run(['node','-e',script],cwd='/var/www/backend',env=env,check=True,timeout=240)


async def bind_owner(state, conversation):
    from campaign_ownership import register_campaign_for_session
    record = await register_campaign_for_session(conversation['session_id'], CAMPAIGN)
    assert record and agent_db()['account_campaign_ownership'].count_documents({'_id':CAMPAIGN,'owner_user_id':state['user_id']}) == 1


def main():
    assert socket.gethostname() == 'momolita'
    mode=sys.argv[1]
    if mode=='init':
        assert not ARTIFACT.exists(), 'Test already initialized'
        state={'campaign_id':CAMPAIGN,'email':'eval-20260831-m2@testing.example',
               'password':secrets.token_urlsafe(24),'started_at':datetime.now(timezone.utc).isoformat()}
        with httpx.Client(timeout=170) as c:
            call(c,'POST','/auth/anonymous')
            user=call(c,'POST','/auth/register',{'email':state['email'],'password':state['password'],'display_name':'Evaluation VPS QA'},expected=201)
            state['user_id']=user['user']['user_id']; state['cookies']=dict(c.cookies); save(state)
            conv=call(c,'POST','/conversations',{'title':'[EVAL QA] Runtime acceptance','experience_mode':'guided','conversation_model':'openai_gpt_5_4_mini'},expected=201)
            # API may wrap the public conversation.
            conv=conv.get('conversation',conv); state['conversation']=conv; save(state)
            assert agent_db()['zalo_threads'].count_documents({'user_id':state['user_id']}) == 0
            seed_reports(state)
            asyncio.run(bind_owner(state,conv))
            workspace=call(c,'GET',f'/evaluation/campaigns/{CAMPAIGN}/scenarios')
            assert workspace['state']['activeRevision']==1 and len(workspace['presets'])==12
            state['initial_workspace_revision']=1; save(state)
            print(json.dumps({'campaign_id':CAMPAIGN,'baseline_revision':1,'presets':12,'account':'isolated QA account; no OA link'}))
        return
    state=json.loads(ARTIFACT.read_text())
    if mode=='bind':
        asyncio.run(bind_owner(state,state['conversation']))
        print('QA ownership verified from server record')
        return
    with client(state) as c:
        prefix=f'/evaluation/campaigns/{CAMPAIGN}'
        if mode=='apply':
            call(c,'PUT',prefix+'/policy',{'enabled':True,'level':'L2'})
            body={'presetId':'click_overlay','targetPlacementId':'ZingNews_Masthead','windowDays':3,
                  'persistenceWindows':2,'impact':0.75,'seed':'vps-qa','requestId':'vps-qa-'+uuid.uuid4().hex,'expectedRevision':1}
            state['scenario_request']=body; save(state)
            preview=call(c,'POST',prefix+'/scenarios/preview',body)
            assert preview['activeRevision']==1
            result=call(c,'POST',prefix+'/scenarios/apply',body)
            state['apply_result']=result; save(state)
            print(json.dumps({'revision':result['scenario']['revision'],'evaluation_status':result['evaluation'].get('status'),
                              'evaluation_error':result['evaluation'].get('error')}))
        elif mode=='poll':
            result=call(c,'GET',prefix)
            jobs=result['investigation_jobs']
            print(json.dumps({'mode':result['investigation_mode'],'incidents':[{k:i.get(k) for k in ['incident_id','issue_type','scope','state','dataset_revision']} for i in result['incidents']],
                'jobs':[{k:j.get(k) for k in ['job_id','status','attempts','model_calls','error','review','tasks']} for j in jobs]},ensure_ascii=False))
            state['latest']=result; save(state)
        elif mode=='qa':
            result=call(c,'GET',prefix)
            incident=next(i for i in result['incidents'] if i['issue_type']=='ctr_regression')
            bundle=incident['investigation']; assert bundle['mode']=='multi_agent'
            body={'question':'Bằng chứng nào cho thấy vùng click bị che? Điều gì vẫn chưa được chứng minh?',
                  'requestId':'qa-question-'+uuid.uuid4().hex,'expectedRevision':2,'expectedBundleId':bundle['bundle_id']}
            path=prefix+'/incidents/'+incident['incident_id']+'/questions'
            response=call(c,'POST',path,body); replay=call(c,'POST',path,body); assert response==replay
            history=call(c,'GET',path); assert len(history['questions'])>=1
            state['qa']=response; state['incident_id']=incident['incident_id']; save(state)
            print(json.dumps(response,ensure_ascii=False))
        elif mode=='security':
            # Use a separate legitimate anonymous identity to test ownership.
            with httpx.Client(timeout=30) as stranger:
                call(stranger,'POST','/auth/anonymous')
                assert stranger.get(BASE+prefix).status_code==404
                r=stranger.post(BASE+prefix+'/runs',json={},headers={'X-CSRF-Token':stranger.cookies.get('aa_csrf')})
                assert r.status_code==404
            rejected=c.post(BASE+prefix+'/policy',json={'enabled':False})
            assert rejected.status_code in (403,405)
            rejected=c.put(BASE+prefix+'/policy',json={'enabled':False})
            assert rejected.status_code==403
            state['cookies']=dict(c.cookies); save(state)
            direct=httpx.post('https://api.pawgrammers.io.vn/api/reports/internal/scenarios/'+CAMPAIGN+'/apply',json=state['scenario_request'])
            assert direct.status_code==401
            replay=call(c,'POST',prefix+'/scenarios/apply',state['scenario_request'])
            assert replay['scenario']['revision']==2 and replay['scenario']['replayed']
            for action in ['prepare_recovery','start_recovery','verify','resolve']:
                r=c.post(BASE+prefix+'/incidents/'+state['incident_id']+'/actions',json={'action':action},headers={'X-CSRF-Token':c.cookies.get('aa_csrf')})
                assert r.status_code==409
            print(json.dumps({'ownership_read_write':'denied','missing_csrf':'denied','direct_backend_mutation':'denied',
                              'scenario_replay':'same revision','L3':'blocked'}))
        elif mode=='disable':
            call(c,'PUT',prefix+'/policy',{'enabled':False})
            print('QA campaign evaluation disabled; no scheduled or OA activity')
        elif mode=='verify':
            for url in ['https://agent.pawgrammers.io.vn/agent/ready',
                        'https://api.pawgrammers.io.vn/api/health']:
                r=c.get(url); assert r.status_code==200
            version=c.get('https://agent.pawgrammers.io.vn/agent/api/version').json()
            assert version['version']=='2026-08-31.1'
            print('DEPLOYED_VERSION',version['version'])
            # Verify public report and Analytics readers agree on the active
            # immutable snapshot, not the retained legacy baseline tables.
            api='https://api.pawgrammers.io.vn/api'
            report_rows=c.get(api+'/reports/data/'+CAMPAIGN).json()
            analytics_rows=c.get(api+'/analytics/data',params={'campaignId':CAMPAIGN}).json()
            analyses=c.get(api+'/reports/analysis/'+CAMPAIGN).json()
            assert len(report_rows)==len(analytics_rows)==20 and len(analyses)==6
            hashes={r['inputHash'] for r in report_rows+analytics_rows+analyses}
            assert len(hashes)==1
            assert sum(r['clicks'] for r in report_rows)==700
            print('PUBLIC_READERS same scenario hash; 20 rows; 6 analyses; 700 clicks')
            result=call(c,'GET',prefix)
            job=next(j for j in result['investigation_jobs'] if j['dataset_revision']==2)
            assert job['status']=='partial' and job['model_calls']==9
            assert job.get('notification_enqueue_count')==0
            history=call(c,'GET',prefix+'/incidents/'+state['incident_id']+'/questions')
            assert len(history['questions'])==1
            q=agent_db()['evaluation_incident_questions'].find_one({'campaign_id':CAMPAIGN})
            assert q and q['status']=='completed'
            script=r'''
require('dotenv').config();const mongoose=require('mongoose');
const S=require('./models/CampaignReportState'),D=require('./models/ReportDataset');
const A=require('./models/AnalyticsRecord'),R=require('./models/ReportAnalysis');
const {activeRecords,activeAnalyses}=require('./services/reportDatasets');
(async()=>{await mongoose.connect(process.env.MONGODB_URI);const campaignId='EVAL-QA-20260831-M2';
const state=await S.findOne({campaignId}).lean(), datasets=await D.find({campaignId}).sort({revision:1}).lean();
// M1 uses immutable snapshots, not replacement of the legacy baseline tables.
const rows=await activeRecords(campaignId), reports=await activeAnalyses(campaignId);
if(state.activeRevision!==2||datasets.length!==2||rows.length!==20||reports.length!==6)throw Error('Revision/count mismatch');
if(!rows.every(r=>r.inputHash===state.activeInputHash)||!reports.every(r=>r.inputHash===state.activeInputHash&&r.status==='ready')){
console.log('PROJECTION_DIAGNOSTIC',JSON.stringify({activeHash:state.activeInputHash,rows:[...new Set(rows.map(r=>r.inputHash))],
reports:reports.map(r=>({type:r.reportType,hash:r.inputHash,status:r.status})),datasets:datasets.map(d=>({revision:d.revision,hash:d.inputHash}))}));
throw Error('Active projection mismatch');}
console.log('REPORT_CONSISTENCY',JSON.stringify({revision:2,datasets:2,rows:20,readyReports:6,sameInputHash:true,
analyses:reports.map(r=>({type:r.reportType,provider:r.provenance?.provider,fallbackReason:r.provenance?.fallbackReason})),
baselineFallbacks:await R.countDocuments({campaignId,'provenance.provider':'deterministic_fallback'})}));
await mongoose.disconnect()})().catch(e=>{console.error(e.message);process.exit(1)});
'''
            env=dict(os.environ)
            # Agent dotenv is already loaded into this process. Do not leak its
            # Mongo URI into the backend check: use the actual backend runtime.
            env.pop('MONGODB_URI',None)
            runtime=next(p['pm2_env'] for p in json.loads(subprocess.check_output(['pm2','jlist'])) if p['name']=='adspilot-api')
            if runtime.get('MONGODB_URI'): env['MONGODB_URI']=runtime['MONGODB_URI']
            subprocess.run(['node','-e',script],cwd='/var/www/backend',env=env,check=True,timeout=30)
            print(json.dumps({'health':'passed','persisted_job_calls':9,'persisted_questions':1,
                              'notification_enqueue_count':0,'qa_policy_enabled':result['policy']['enabled']}))


if __name__=='__main__': main()
