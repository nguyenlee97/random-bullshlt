const test = require('node:test');
const assert = require('node:assert/strict');

const { buildOpenAIRequestBody } = require('../services/reportGenerator');


test('GPT-5 report calls use max_completion_tokens without unsupported temperature', () => {
  const body = buildOpenAIRequestBody(
    'gpt-5.4-mini', [{ role: 'user', content: 'report' }], 0.6, 8000
  );
  assert.equal(body.max_completion_tokens, 8000);
  assert.equal('max_tokens' in body, false);
  assert.equal('temperature' in body, false);
  assert.deepEqual(body.response_format, { type: 'json_object' });
});


test('older report models retain their configured sampling temperature', () => {
  const body = buildOpenAIRequestBody(
    'gpt-4.1-mini', [{ role: 'user', content: 'report' }], 0.6, 8000
  );
  assert.equal(body.temperature, 0.6);
});
