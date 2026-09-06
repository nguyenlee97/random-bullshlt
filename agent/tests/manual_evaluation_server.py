"""Loopback-only UI fixture. No Mongo, model API, report service or Zalo sending.

Run from agent/: python -m tests.manual_evaluation_server
Start Agent UI with VITE_AGENT_URL and VITE_BACKEND_URL=http://localhost:18765.
Open Analytics with ?apiBase=http://localhost:18765/api.
This verifies UI integration, not production authentication or Mongo semantics.
"""
import json
from copy import deepcopy
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from evaluation import routes, service, store, investigator
from tests.test_l2_investigation import baseline_records, apply_scenario, ORDER, ZONE_MAP, BASELINE_INPUT
import zalo_incidents

CAMPAIGN = 'ORD-2026-001'
BASELINE = baseline_records()
DATA = {'state': {'activeRevision': 1},
        'baseline': {'records': BASELINE, 'input': BASELINE_INPUT},
        'active': {'records': deepcopy(BASELINE), 'input': BASELINE_INPUT}}
REVISIONS = [{'revision': 1, 'kind': 'baseline', 'status': 'ready'}]
REQUESTS = {}
PRESETS = [
    ('healthy_baseline', 'Healthy baseline'), ('low_impression_zone', 'Low impression — một zone'),
    ('low_ctr', 'Normal impression, low CTR'), ('creative_failure', 'Creative render/format failure'),
    ('click_tracking_failure', 'Click area/event failure'), ('config_drift', 'Campaign configuration drift'),
    ('poor_placement', 'Poor placement'), ('tracking_delay', 'Tracking delay / insufficient data'),
    ('multiple_issues', 'Multiple issues'), ('recovery_success', 'Recovery successful'),
    ('recovery_ineffective', 'Recovery ineffective'),
]


async def no_db():
    return None


async def order(_campaign):
    return deepcopy(ORDER)


async def catalog():
    return deepcopy(ZONE_MAP)


async def no_notify(*_args, **_kwargs):
    return 0


async def owned(_request, campaign_id):
    if campaign_id != CAMPAIGN:
        raise HTTPException(404, 'fixture campaign not found')
    return {'user_id': 'local-fixture-only'}


async def report_request(method, path, json=None):
    if '/datasets/' in path:
        return deepcopy(DATA)
    if method == 'GET':
        return {'campaignId': CAMPAIGN, 'state': DATA['state'], 'revisions': list(reversed(REVISIONS)),
                'placements': list(ORDER['placements']),
                'presets': [{'id': key, 'label': label} for key, label in PRESETS]}
    body = json or {}
    transformed = apply_scenario(BASELINE, body['presetId'],
        target=body.get('targetPlacementId') or ORDER['placements'][0],
        window_days=body.get('windowDays', 3), persistence=body.get('persistenceWindows', 2),
        impact=body.get('impact', .75))
    if path.endswith('/preview'):
        return {'records': transformed, 'beforeRecords': deepcopy(DATA['active']['records']),
                'activeRevision': DATA['state']['activeRevision'], 'scenario': body}
    if path.endswith('/apply'):
        request_id = body['requestId']
        if request_id in REQUESTS:
            return {**REQUESTS[request_id], 'replayed': True}
        if body['expectedRevision'] != DATA['state']['activeRevision']:
            raise service.ReportServiceError('Dataset revision changed; preview again', 409)
        DATA['state']['activeRevision'] += 1
        DATA['active']['records'] = transformed
        revision = DATA['state']['activeRevision']
        REVISIONS.append({'revision': revision, 'scenario': body, 'status': 'published'})
        result = {'revision': revision, 'campaignId': CAMPAIGN, 'inputHash': str(uuid4())}
        REQUESTS[request_id] = result
        return result
    raise RuntimeError('unimplemented fixture path')


def make_app():
    store._collections = no_db
    service.report_request = report_request
    investigator._load_order = order
    investigator._load_zone_map = catalog
    zalo_incidents.notify_incidents = no_notify
    routes.report_request = report_request
    routes._assert_campaign_access = owned
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=[
        'http://localhost:5174', 'http://localhost:5175',
        'http://127.0.0.1:5174', 'http://127.0.0.1:5175'],
        allow_credentials=True, allow_methods=['GET', 'POST', 'PUT'], allow_headers=['*'])
    app.include_router(routes.evaluation_router, prefix='/api/agent')

    @app.post('/api/agent/auth/anonymous')
    async def anonymous():
        return {'anonymous_id': 'local-fixture', 'identity_id': 'local-fixture'}

    @app.get('/api/agent/auth/me')
    async def me():
        return {'user': None, 'anonymous_id': 'local-fixture', 'authenticated': False}

    @app.get('/api/agent/campaigns')
    async def campaigns():
        return {'campaigns': [{
            'entry_id': 'campaign:' + CAMPAIGN, 'campaign_id': CAMPAIGN,
            'title': 'Evaluation QA — local fixture', 'phase': 'operational', 'lifecycle': 'active',
            'experience_mode': 'copilot', 'order_ids': [CAMPAIGN],
            'order': {'id': CAMPAIGN, 'budget': 100000000, 'objective': 'awareness',
                      'placement_count': 2, 'creative_count': 2, 'order_count': 1},
            'routes': {'manage': '/manage/campaigns/' + CAMPAIGN},
        }]}

    @app.get('/api/analytics/data')
    @app.get('/api/reports/data/{campaign_id}')
    async def records(campaign_id: str = CAMPAIGN):
        return DATA['active']['records']

    @app.get('/api/orders')
    async def orders():
        return [{**ORDER, 'orderId': CAMPAIGN, 'brand': 'Evaluation QA — local fixture'}]

    @app.get('/api/health')
    @app.get('/health')
    async def health():
        return {'status': 'ok'}

    @app.get('/api/reports/status/{campaign_id}')
    async def status(campaign_id: str):
        return {'status': 'ready', 'ready': True, 'readyCount': 6, 'total': 6}

    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(make_app(), host='127.0.0.1', port=18765)
