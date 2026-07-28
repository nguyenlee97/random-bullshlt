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
  LOCAL_SMONEY_URL: 'http://localhost:5179',
  LOCAL_DICUNGCON_URL: 'http://localhost:5180',
  LOCAL_ZAGOO_URL: 'http://localhost:5181',
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
  assert.equal(
    publicSiteUrl({ siteId: 'smoney', channel: 'smoney-site' }, localEnv),
    'http://localhost:5179/'
  );
  assert.equal(
    publicSiteUrl({ siteId: 'dicungcon', channel: 'dicungcon-site' }, localEnv),
    'http://localhost:5180/'
  );
  assert.equal(
    publicSiteUrl({ siteId: 'zagoo', channel: 'zagoo-site' }, localEnv),
    'http://localhost:5181/'
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

test('NP-6 category links retain their topic route in local mode', () => {
  const placement = {
    siteId: 'baomoi',
    channel: 'baomoi-family-parenting',
    pageTemplate: 'category',
    siteUrl: 'https://baomoi-stg.pawgrammers.io.vn/category.html?topic=family-parenting',
  };
  assert.equal(
    publicSiteUrl(placement, localEnv),
    'http://localhost:5177/category.html?topic=family-parenting',
  );

  assert.equal(
    publicSiteUrl({
      ...placement,
      siteId: 'znews',
      channel: 'znews-family-parenting',
      siteUrl: 'https://znews-stg.pawgrammers.io.vn/gia-dinh.html',
    }, localEnv),
    'http://localhost:5176/gia-dinh.html',
  );
});

test('ad serving excludes soft-deleted campaigns', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'routes', 'ads.js'), 'utf8');
  assert.match(source, /status: 'active',[\s\S]*deletedAt: null,[\s\S]*placements: zone/);
});
