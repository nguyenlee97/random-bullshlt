"""Loopback UI harness: real L1/queue/orchestrator/Chromium, scripted model.

No provider, OA, authentication, or Mongo validation. Never deploy this module.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from config import config
from evaluation import investigation_jobs, investigation_worker, multi_agent, service, routes, store, questions
from tests import manual_evaluation_server as base
from tests.test_investigation_jobs import MemoryJobCollection
from tests.test_multi_agent_investigation import scenario, ScriptedModel


def make_app():
    app = base.make_app()
    app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5176', 'http://127.0.0.1:5176'],
                       allow_credentials=True, allow_methods=['GET', 'POST', 'PUT'], allow_headers=['*'])
    config.EVALUATION_MULTI_AGENT_ENABLED = True
    config.OPENAI_API_KEY = 'test-only-never-sent'
    col, question_col, model = MemoryJobCollection(), MemoryJobCollection(), ScriptedModel()
    failures_left = 2 if os.environ.get('EVAL_UI_TIMEOUT_ONCE') == '1' else 0
    base.PRESETS.append(('click_overlay', 'Click area covered — inspect rendered page'))

    async def collection():
        return col

    async def question_collection():
        return question_col

    async def delayed_model(*args, **kwargs):
        nonlocal failures_left
        await asyncio.sleep(.6)  # expose running states to UI polling
        if failures_left and args[0] == 'creative' and args[1].get('evidence'):
            from evaluation.decision_contract import ModelResponseError
            failures_left -= 1
            raise ModelResponseError('model_timeout')
        return await model(*args, **kwargs)

    async def request(method, path, json=None):
        result = await base.report_request(method, path, json)
        if path.endswith('/apply') and not result.get('replayed'):
            params = {k: v for k, v in (json or {}).items() if k != 'presetId'}
            base.DATA['active']['runtimeFixture'] = scenario(json['presetId'], **params)['runtimeFixture']
        return result

    investigation_jobs.collection = collection
    questions.collection = question_collection
    questions.decide = delayed_model
    questions.report_request = request
    multi_agent.decide = delayed_model
    service.report_request = request
    routes.report_request = request

    @asynccontextmanager
    async def lifespan(_app):
        await store.save_policy(base.CAMPAIGN, {'level': 'L2'})
        await investigation_worker.start_worker()
        try:
            yield
        finally:
            await investigation_worker.stop_worker()

    app.router.lifespan_context = lifespan
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(make_app(), host='127.0.0.1', port=18766)
