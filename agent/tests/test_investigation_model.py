from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from config import config
from evaluation.agent_model import Decision, decide
from tests.test_multi_agent_investigation import decision


@pytest.mark.asyncio
async def test_model_protocol_is_bounded_stateless_and_uses_no_campaign_session(monkeypatch):
    import openai, metrics
    monkeypatch.setattr(config, 'EVALUATION_MULTI_AGENT_ENABLED', True)
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'test-only')
    parsed = Decision.model_validate(decision(assessment='insufficient_evidence'))
    parse = AsyncMock(return_value=SimpleNamespace(status='completed', output_parsed=parsed))
    client = AsyncMock()
    client.__aenter__.return_value = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    factory = Mock(return_value=client)
    monkeypatch.setattr(openai, 'AsyncOpenAI', factory)
    record = Mock()
    monkeypatch.setattr(metrics, 'record_llm_call', record)
    result = await decide('creative', {'scope': 'zone-a', 'evidence': []}, tools={'inspect_render': 'Read only'}, image='test-png')
    assert result['assessment'] == 'insufficient_evidence'
    kwargs = parse.call_args.kwargs
    assert kwargs['store'] is False and kwargs['max_output_tokens'] == 2400
    assert kwargs['text_format'] is Decision
    assert 'previous_response_id' not in kwargs
    assert 'campaign_session' not in kwargs
    assert kwargs['input'][0]['content'][1]['type'] == 'input_image'
    assert factory.call_args.kwargs['max_retries'] == 0
    assert record.call_args.kwargs['outcome'] == 'ok'
    parse.return_value = SimpleNamespace(status='incomplete', output_parsed=parsed)
    with pytest.raises(RuntimeError, match='complete structured'):
        await decide('creative', {}, tools={})
    assert record.call_args.kwargs['outcome'] == 'error'


@pytest.mark.asyncio
async def test_disabled_model_does_not_create_a_client(monkeypatch):
    import openai
    monkeypatch.setattr(config, 'EVALUATION_MULTI_AGENT_ENABLED', False)
    factory = Mock()
    monkeypatch.setattr(openai, 'AsyncOpenAI', factory)
    with pytest.raises(RuntimeError, match='not configured'):
        await decide('creative', {}, tools={})
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_provider_refusal_and_errors_have_safe_distinct_codes(monkeypatch):
    import openai, metrics
    from evaluation.decision_contract import ModelResponseError
    monkeypatch.setattr(config, 'EVALUATION_MULTI_AGENT_ENABLED', True)
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'test-only')
    parse=AsyncMock(return_value=SimpleNamespace(status='completed',output_parsed=None,
        output=[SimpleNamespace(content=[SimpleNamespace(type='refusal')])]))
    client=AsyncMock(); client.__aenter__.return_value=SimpleNamespace(responses=SimpleNamespace(parse=parse))
    monkeypatch.setattr(openai,'AsyncOpenAI',Mock(return_value=client))
    monkeypatch.setattr(metrics,'record_llm_call',Mock())
    with pytest.raises(ModelResponseError) as error:
        await decide('creative',{},tools={})
    assert error.value.code=='model_refusal'
    for exc,code in [(TimeoutError('private timeout details'),'model_timeout'),
                     (RuntimeError('secret-provider-body'),'model_unavailable')]:
        parse.side_effect=exc
        with pytest.raises(ModelResponseError) as error:
            await decide('creative',{},tools={})
        assert error.value.code==code and str(exc) not in str(error.value)
