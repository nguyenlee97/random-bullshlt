const test = require('node:test');
const assert = require('node:assert/strict');

const {
  deterministicUploadFilename,
} = require('../lib/creativeUploadIdempotency');

test('creative upload retries resolve to one deterministic filename', () => {
  const key = 'openai-creative:conv-123:demo-zplay-znews-top-banner:1833769';
  const first = deterministicUploadFilename(key, 'znews-top-banner.png');
  const retry = deterministicUploadFilename(key, 'znews-top-banner.png');

  assert.equal(first, retry);
  assert.match(first, /^creative_upload_[a-f0-9]{24}\.png$/);
  assert.notEqual(
    first,
    deterministicUploadFilename(`${key}:different`, 'znews-top-banner.png'),
  );
});
