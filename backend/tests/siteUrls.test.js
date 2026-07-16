const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { publicSiteUrl, withPublicSiteUrl } = require('../lib/siteUrls');

const localEnv = {
  SITE_URL_MODE: 'local',
  LOCAL_ZNEWS_URL: 'http://localhost:5176',
  LOCAL_BAOMOI_URL: 'http://localhost:5177',
  LOCAL_ZINGMP3_URL: 'http://localhost:5178',
};

test('local zone links point to the matching local mock site and category', () => {
  assert.equal(
    publicSiteUrl({ siteId: 'znews', channel: 'znews-cong-nghe' }, localEnv),
    'http://localhost:5176/cong-nghe.html'
  );
  assert.equal(
    publicSiteUrl({ siteId: 'baomoi', channel: 'baomoi-site' }, localEnv),
    'http://localhost:5177/'
  );
  assert.equal(
    publicSiteUrl({ siteId: 'zingmp3', channel: 'zingmp3-site' }, localEnv),
    'http://localhost:5178/'
  );
});

test('hosted links remain unchanged outside local mode', () => {
  const placement = {
    siteId: 'znews', channel: 'znews-giai-tri',
    siteUrl: 'https://znews-stg.pawgrammers.io.vn/giai-tri.html',
  };
  assert.equal(publicSiteUrl(placement, { SITE_URL_MODE: 'hosted' }), placement.siteUrl);
  assert.equal(withPublicSiteUrl(placement, { SITE_URL_MODE: 'hosted' }).siteUrl, placement.siteUrl);
});

test('ad serving excludes soft-deleted campaigns', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'routes', 'ads.js'), 'utf8');
  assert.match(source, /status: 'active',[\s\S]*deletedAt: null,[\s\S]*placements: zone/);
});
