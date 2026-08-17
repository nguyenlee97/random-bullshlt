const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const { TOPICS } = require('../seed/np6-catalog');

const root = path.join(__dirname, '..', '..');

function read(...parts) {
  return fs.readFileSync(path.join(root, ...parts), 'utf8');
}

const activeTopics = TOPICS.filter((topic) => topic.lifecycleStatus === 'active');

test('BaoMoi reusable renderer covers the exact 23-topic active taxonomy', () => {
  const baomoi = read('baomoi_replicate', 'category-v2.js');

  assert.equal(TOPICS.length, 25);
  assert.equal(activeTopics.length, 23);
  for (const topic of activeTopics) {
    const tuple = `['${topic.slug}','${topic.code}'`;
    assert.ok(baomoi.includes(tuple), `BaoMoi missing ${topic.id}`);
  }
});

test('each active ZNews topic uses a static category route with four exact zones', () => {
  const legacyCodes = {
    business_finance: 'KinhDoanh',
    health_wellness: 'SucKhoe',
    sports_outdoors: 'TheThao',
    technology_science: 'CongNghe',
  };
  for (const topic of activeTopics) {
    assert.match(topic.znewsPath, /^\/[a-z0-9-]+\.html$/);
    const html = read('znews_replicate', topic.znewsPath.slice(1));
    for (const suffix of [
      'Masthead',
      'SideLeft',
      'SideRight',
      'SidebarBox',
    ]) {
      const code = suffix === 'Masthead'
        ? topic.code
        : (legacyCodes[topic.id] || topic.code);
      const id = `Znews_${code}_${suffix}`;
      assert.match(html, new RegExp(`data-zone="${id}"`), `${topic.id} missing ${id}`);
    }
    assert.doesNotMatch(html, /data-zone="Znews_[A-Za-z]+_Background"/);
    assert.match(html, /np6-topic-page\.js/);
    assert.match(html, /api\.js/);
  }
});

test('no retained ZNews category route exposes a background mount', () => {
  for (const topic of TOPICS) {
    const html = read('znews_replicate', topic.znewsPath.slice(1));
    assert.doesNotMatch(
      html,
      /data-zone="Znews_[A-Za-z]+_Background"/,
      `${topic.id} still exposes a category background`,
    );
  }
});

test('the shared ZNews runtime restores an accessible 23-topic mega menu', () => {
  const runtime = read('znews_replicate', 'np6-topic-page.js');
  assert.equal((runtime.match(/^\s+\['[^']+', '[a-z0-9-]+\.html'\],$/gm) || []).length, 23);
  assert.match(runtime, /mouseenter/);
  assert.match(runtime, /aria-expanded/);
  assert.match(runtime, /event\.key === 'Escape'/);
  assert.match(runtime, /event\.key === 'ArrowDown'/);
  assert.match(runtime, /np6-channel-bar/);
});

test('the ZNews homepage loads the shared menu runtime without category layout CSS', () => {
  const homepage = read('znews_replicate', 'index.html');
  assert.match(homepage, /znews-menu\.css\?v=np6-2026-02-home-menu-1/);
  assert.match(homepage, /np6-topic-page\.js\?v=np6-2026-02-home-menu-1/);
  assert.doesNotMatch(homepage, /category-style\.css/);
});

test('the 19 generated ZNews categories contain local topic images and synthetic stories', () => {
  const generated = activeTopics.filter((topic) => ![
    'business_finance',
    'health_wellness',
    'sports_outdoors',
    'technology_science',
  ].includes(topic.id));
  assert.equal(generated.length, 19);
  for (const topic of generated) {
    const html = read('znews_replicate', topic.znewsPath.slice(1));
    assert.equal((html.match(/article-id="np6-/g) || []).length, 35, topic.id);
    assert.equal((html.match(/assets\/np6-topics\//g) || []).length, 35, topic.id);
    assert.doesNotMatch(html, /href="https:\/\/znews\.vn\/[^"]+-post\d+\.html/);
  }
});

test('the discarded generic ZNews renderer is no longer a route', () => {
  assert.equal(fs.existsSync(path.join(root, 'znews_replicate', 'category.html')), false);
  assert.equal(fs.existsSync(path.join(root, 'znews_replicate', 'category-v2.js')), false);
  assert.equal(fs.existsSync(path.join(root, 'znews_replicate', 'category-v2.css')), false);
});

test('BaoMoi category placement IDs reuse rendering without homepage coupling', () => {
  const api = read('baomoi_replicate', 'api.js');
  const shell = read('baomoi_replicate', 'category.html');
  const style = read('baomoi_replicate', 'category-v2.css');
  const category = read('baomoi_replicate', 'category-v2.js');
  assert.match(api, /endsWith\('_Background'\)/);
  assert.match(api, /endsWith\('_SideLeft'\)/);
  assert.match(api, /endsWith\('_SideRight'\)/);
  assert.match(api, /endsWith\('_SidebarBox'\)/);
  assert.match(shell, /BÁO MỚI/);
  assert.match(shell, />NÓNG</);
  assert.match(shell, />MỚI</);
  assert.match(shell, />VIDEO</);
  assert.match(shell, />CHỦ ĐỀ</);
  assert.match(shell, /baomoi-static\.bmcdn\.me\/web\/styles\/img\/bm-logo-v3\.png/);
  assert.match(shell, /fonts\/text-font\/lexend\/styles\.css/);
  assert.match(shell, /category-skin-spacer/);
  assert.match(style, /\.main-nav \{ background: #2fa1b3; \}/);
  assert.match(style, /grid-template-columns: 260px minmax\(0, 530px\)/);
  assert.match(category, /assets\/np6-topics\/\$\{slug\}-/);
  assert.match(category, /description:/);
  assert.doesNotMatch(category, /data:image\/svg\+xml/);
  assert.match(category, /!result\?\.hasAd \|\| !result\.html/);
  assert.doesNotMatch(category, /result\.ad\.html/);
  assert.match(category, /document\.body\.style\.backgroundImage/);
  assert.match(api, /BaoMoi_Masthead'\)\s+return 'ad-pic\/background-ad\.jpg'/);
  assert.match(api, /isFallback:\s+false/);
  assert.match(api, /hasAd: true, isFallback: true/);
  assert.match(category, /const showBackground = hasBackground && \(backgroundIsLive \|\| !mastheadIsLive\)/);
  assert.match(category, /mountAd\(\s*`\$\{prefix\}_Masthead`/);
  assert.match(category, /mountAd\(\s*`\$\{prefix\}_Background`/);
  assert.doesNotMatch(category, /Masthead banner hidden/);
});

function renderedBaoMoiZoneIds(topic) {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) {
      elements.set(id, { id, dataset: {}, innerHTML: '', textContent: '' });
    }
    return elements.get(id);
  };
  let onReady = null;
  const document = {
    title: '',
    getElementById: element,
    addEventListener(name, callback) {
      if (name === 'DOMContentLoaded') onReady = callback;
    },
  };
  const source = read('baomoi_replicate', 'category-v2.js');
  vm.runInNewContext(source, {
    document,
    location: { search: `?topic=${topic.slug}` },
    URLSearchParams,
    encodeURIComponent,
    fetchAdForZone: async () => ({ hasAd: false }),
  });
  assert.ok(onReady, 'BaoMoi did not register DOMContentLoaded');
  onReady();
  return [
    'category-masthead',
    'category-background',
    'category-side-left',
    'category-side-right',
    'category-sidebar',
  ].map((id) => element(id).dataset.zone);
}

test('all 23 active topics produce the exact five BaoMoi catalog placement IDs', () => {
  for (const topic of activeTopics) {
    assert.deepEqual(
      renderedBaoMoiZoneIds(topic),
      [
        `BaoMoi_${topic.code}_Masthead`,
        `BaoMoi_${topic.code}_Background`,
        `BaoMoi_${topic.code}_SideLeft`,
        `BaoMoi_${topic.code}_SideRight`,
        `BaoMoi_${topic.code}_SidebarBox`,
      ],
    );
  }
});

async function renderedBaoMoiHeroAds(background, masthead) {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) {
      elements.set(id, {
        id,
        dataset: {},
        innerHTML: '',
        textContent: '',
        classList: { add() {} },
        querySelector() { return null; },
      });
    }
    return elements.get(id);
  };
  const bodyClasses = new Set();
  const body = {
    classList: {
      add(name) { bodyClasses.add(name); },
      remove(name) { bodyClasses.delete(name); },
    },
    style: { backgroundImage: '' },
  };
  let onReady = null;
  vm.runInNewContext(read('baomoi_replicate', 'category-v2.js'), {
    document: {
      title: '',
      body,
      getElementById: element,
      addEventListener(name, callback) {
        if (name === 'DOMContentLoaded') onReady = callback;
      },
    },
    location: { search: '?topic=music-live-events' },
    URLSearchParams,
    encodeURIComponent,
    fetchAdForZone: async (zoneId) => {
      if (zoneId.endsWith('_Background')) return background;
      if (zoneId.endsWith('_Masthead')) return masthead;
      return { hasAd: false, html: '' };
    },
  });
  onReady();
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
  return {
    background: element('category-background').innerHTML,
    masthead: element('category-masthead').innerHTML,
    hasBackgroundClass: bodyClasses.has('has-bg-ad'),
  };
}

test('BaoMoi background and masthead are mutually exclusive', async () => {
  const bothFallback = await renderedBaoMoiHeroAds(
    { hasAd: true, isFallback: true, html: '<b>background fallback</b>', imageUrl: 'skin.jpg' },
    { hasAd: true, isFallback: true, html: '<b>masthead fallback</b>' },
  );
  assert.match(bothFallback.background, /background fallback/);
  assert.equal(bothFallback.masthead, '');
  assert.equal(bothFallback.hasBackgroundClass, true);

  const liveMasthead = await renderedBaoMoiHeroAds(
    { hasAd: true, isFallback: true, html: '<b>background fallback</b>', imageUrl: 'skin.jpg' },
    { hasAd: true, isFallback: false, html: '<b>live masthead</b>' },
  );
  assert.equal(liveMasthead.background, '');
  assert.match(liveMasthead.masthead, /live masthead/);
  assert.equal(liveMasthead.hasBackgroundClass, false);

  const bothLive = await renderedBaoMoiHeroAds(
    { hasAd: true, isFallback: false, html: '<b>live background</b>', imageUrl: 'skin.jpg' },
    { hasAd: true, isFallback: false, html: '<b>live masthead</b>' },
  );
  assert.match(bothLive.background, /live background/);
  assert.equal(bothLive.masthead, '');
});

const PROPERTY_RENDERERS = {
  smoney_replicate: [
    'SMoney_TopPromo_Desktop',
    'SMoney_TopPromo_Mobile',
    'SMoney_StockScreener_InContent_Desktop',
    'SMoney_StockScreener_InContent_Mobile',
  ],
  dicungcon_replicate: [
    'DiCungCon_ContentBridge_Desktop',
    'DiCungCon_ContentBridge_Mobile',
    'DiCungCon_SidebarRail_Desktop',
  ],
  zagoo_replicate: [
    'Zagoo_Interstitial_Desktop',
    'Zagoo_Interstitial_Mobile',
  ],
};

test('S-Money, Đi Cùng Con, and Zagoo expose exactly the nine catalog mount points', () => {
  for (const [publisher, zoneIds] of Object.entries(PROPERTY_RENDERERS)) {
    const html = read(publisher, 'index.html');
    assert.match(html, /app\.js/);
    for (const zoneId of zoneIds) {
      assert.match(html, new RegExp(`id="${zoneId}"`), `${publisher} missing ${zoneId}`);
      assert.match(html, new RegExp(`data-zone="${zoneId}"`), `${publisher} missing data-zone`);
    }
  }
});

test('Zagoo discovery carousel uses four distinct game cover images', () => {
  const html = read('zagoo_replicate', 'index.html');
  const carousel = html.match(/<div class="game-carousel">([\s\S]*?)<\/div>\s*<\/section>/)?.[1] || '';
  const covers = [...carousel.matchAll(/<article><img src="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(covers.length, 4);
  assert.equal(new Set(covers).size, 4);
});

async function requestedPropertyZones(publisher, mobile) {
  const requests = [];
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) {
      elements.set(id, {
        id,
        innerHTML: '',
        classList: { add() {} },
        addEventListener() {},
        querySelector() { return null; },
      });
    }
    return elements.get(id);
  };
  let onReady = null;
  const source = read(publisher, 'app.js');
  vm.runInNewContext(source, {
    window: { __ADSTACK_CONFIG__: { allowFallbackAds: true } },
    location: { hostname: 'localhost' },
    document: {
      getElementById: element,
      addEventListener(name, callback) {
        if (name === 'DOMContentLoaded') onReady = callback;
      },
    },
    matchMedia: () => ({ matches: mobile }),
    fetch: async (url) => {
      requests.push(String(url));
      return { ok: false, json: async () => ({ ad: null }) };
    },
    AbortSignal,
    encodeURIComponent,
  });
  assert.ok(onReady, `${publisher} did not register DOMContentLoaded`);
  onReady();
  await new Promise((resolve) => setImmediate(resolve));
  return requests
    .filter((url) => url.includes('/ads/check?'))
    .map((url) => new URL(url).searchParams.get('zone'));
}

test('property renderers request only device-appropriate inventory after reload', async () => {
  assert.deepEqual(
    await requestedPropertyZones('smoney_replicate', false),
    ['SMoney_TopPromo_Desktop', 'SMoney_StockScreener_InContent_Desktop'],
  );
  assert.deepEqual(
    await requestedPropertyZones('smoney_replicate', true),
    ['SMoney_TopPromo_Mobile', 'SMoney_StockScreener_InContent_Mobile'],
  );
  assert.deepEqual(
    await requestedPropertyZones('dicungcon_replicate', false),
    ['DiCungCon_ContentBridge_Desktop', 'DiCungCon_SidebarRail_Desktop'],
  );
  assert.deepEqual(
    await requestedPropertyZones('dicungcon_replicate', true),
    ['DiCungCon_ContentBridge_Mobile'],
  );
  assert.deepEqual(
    await requestedPropertyZones('zagoo_replicate', false),
    ['Zagoo_Interstitial_Desktop'],
  );
  assert.deepEqual(
    await requestedPropertyZones('zagoo_replicate', true),
    ['Zagoo_Interstitial_Mobile'],
  );
});

test('unapproved DCC in-feed and Zagoo native placements are not invented', () => {
  const sources = [
    read('dicungcon_replicate', 'index.html'),
    read('dicungcon_replicate', 'app.js'),
    read('zagoo_replicate', 'index.html'),
    read('zagoo_replicate', 'app.js'),
  ].join('\n');
  assert.doesNotMatch(sources, /DiCungCon_InFeed_Mobile/);
  assert.doesNotMatch(sources, /Zagoo_SponsoredNative/);
});
