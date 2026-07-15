const test = require('node:test');
const assert = require('node:assert/strict');

const { redact, redactText } = require('../middleware/redact');

test('redacts PII, credentials, and sensitive keys recursively', () => {
  const safe = redact({
    email: 'operator@example.com',
    phone: '0901234567',
    citizenId: '079203001234',
    authorization: 'Bearer should-never-survive',
    nested: { password: 'secret-value', note: 'call +84901234567' },
  });
  assert.equal(safe.email, '[REDACTED_EMAIL]');
  assert.equal(safe.phone, '[REDACTED_PHONE]');
  assert.equal(safe.citizenId, '[REDACTED_CCCD]');
  assert.equal(safe.authorization, '[REDACTED]');
  assert.equal(safe.nested.password, '[REDACTED]');
  assert.equal(safe.nested.note, 'call [REDACTED_PHONE]');
});

test('redacts Mongo credentials without retaining the password', () => {
  const safe = redactText('mongo' + 'db://agent:password@mongo.example/campaigns');
  assert.equal(safe, 'mongodb://[REDACTED]@mongo.example/campaigns');
  assert.ok(!safe.includes('password'));
});
