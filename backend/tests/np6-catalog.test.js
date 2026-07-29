const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { readWorksheetRows } = require('../seed/workbook-rows');
const { buildLegacyZonesCatalog, buildZonesCatalog } = require('../seed');
const ZoneCatalog = require('../models/Zone');
const Campaign = require('../models/Campaign');

async function workbookRows() {
  const raw = await readWorksheetRows(
    path.join(__dirname, '..', 'seed', 'data', 'Ads Zone.xlsx'),
    'Ad Zones',
  );
  return raw.map((row) => ({
    mockId: row['Zone ID'],
    reach: row.Reach || 0,
    vi: row['VI %'] || 0,
    ctr: row['CTR %'] || 0,
    cpm: row['CPM VND'] || 0,
    obj: row['Best For'] || 'awareness',
    note: row.Notes || '',
  }));
}

test('NP-6 v2 retains 35 legacy plus 214 category and 9 property placements', async () => {
  const rows = await workbookRows();
  const legacy = buildLegacyZonesCatalog(rows);
  const catalog = buildZonesCatalog(rows);

  assert.equal(legacy.placements.length, 35);
  assert.equal(catalog.placements.length, 258);
  assert.equal(catalog.placements.length - legacy.placements.length, 223);
  assert.equal(new Set(catalog.placements.map((placement) => placement.id)).size, 258);
  assert.equal(catalog.catalogVersion, 'np6-2026-04');
  assert.equal(catalog.topicTaxonomy.length, 25);
  assert.equal(
    catalog.topicTaxonomy.filter((topic) => topic.lifecycleStatus === 'active').length,
    23,
  );
});

test('all NP-6 placements have durable context, contracts, and honest lifecycle state', async () => {
  const catalog = buildZonesCatalog(await workbookRows());
  const contractIds = new Set(catalog.creativeContracts.map((contract) => contract.id));
  const additions = catalog.placements.filter(
    (placement) => placement.catalogVersion === 'np6-2026-04',
  );

  assert.equal(additions.length, 223);
  for (const placement of additions) {
    assert.ok(placement.topicId, placement.id);
    assert.ok(placement.placementFamily, placement.id);
    assert.ok(contractIds.has(placement.creativeContractId), placement.id);
    assert.equal(placement.audienceContext.primaryTopics[0], placement.topicId);
    assert.equal(placement.metricSource, 'synthetic_inventory_v3');
    if (placement.placementFamily === 'category_masthead') {
      assert.equal(placement.lifecycleStatus, 'retired');
      assert.equal(placement.provenance.commercialStatus, 'unavailable');
      assert.equal(
        placement.provenance.retirementReason,
        'category_page_skin_mode_hides_masthead',
      );
    } else {
      assert.equal(placement.lifecycleStatus, 'active');
    }
  }
});

test('all active placements have audience metadata, including the 35 legacy IDs', async () => {
  const catalog = buildZonesCatalog(await workbookRows());
  const active = catalog.placements.filter(
    (placement) => placement.lifecycleStatus === 'active',
  );

  assert.equal(active.length, 204);
  for (const placement of active) {
    assert.ok(placement.topicId, placement.id);
    assert.ok(placement.audienceContext, placement.id);
    assert.ok(placement.audienceContext.primaryTopics.length > 0, placement.id);
    assert.ok(placement.audienceContext.contextScope || placement.catalogVersion === 'np6-2026-04');
  }

  const broadHomepage = active.find((placement) => placement.id === 'ZingNews_Masthead');
  assert.equal(broadHomepage.topicId, 'society_news_law');
  assert.equal(broadHomepage.audienceContext.contextScope, 'broad_news_homepage');
  assert.equal(broadHomepage.audienceContext.confidence, 0.55);

  const musicHomepage = active.find((placement) => placement.id === 'ZingMP3_Masthead');
  assert.equal(musicHomepage.topicId, 'music_live_events');
  assert.equal(musicHomepage.audienceContext.contextScope, 'publisher_vertical');
});

test('the three observed properties add exactly nine provenance-aware placements', async () => {
  const catalog = buildZonesCatalog(await workbookRows());
  const expected = { smoney: 4, dicungcon: 3, zagoo: 2 };

  for (const [siteId, count] of Object.entries(expected)) {
    const placements = catalog.placements.filter((placement) => placement.siteId === siteId);
    assert.equal(placements.length, count, siteId);
    for (const placement of placements) {
      assert.equal(placement.comparisonGroupId, null, placement.id);
      assert.equal(placement.device.length, 1, placement.id);
      assert.equal(placement.renderer.previewSupported, true, placement.id);
      assert.match(placement.siteUrl, new RegExp(`https://${siteId}-stg\\.pawgrammers\\.io\\.vn/`));
      assert.ok(placement.provenance.classification, placement.id);
      assert.ok(placement.provenance.commercialStatus, placement.id);
      assert.ok(placement.provenance.evidenceIds.length > 0, placement.id);
    }
  }

  const zagoo = catalog.placements.filter((placement) => placement.siteId === 'zagoo');
  assert.ok(zagoo.every((placement) => placement.format === 'interstitial'));
  assert.ok(zagoo.every((placement) => placement.provenance.classification === 'observed_house'));
  assert.equal(
    catalog.placements.find((placement) => placement.id === 'DiCungCon_SidebarRail_Desktop')
      .provenance.classification,
    'reserved_layout',
  );
});

test('every recommendable topic and family has a cross-publisher comparison pair', async () => {
  const catalog = buildZonesCatalog(await workbookRows());
  const requiredFamilies = [
    'category_background',
    'category_side_left',
    'category_side_right',
    'category_sidebar',
  ];

  for (const topic of catalog.topicTaxonomy.filter(
    (item) => item.lifecycleStatus === 'active'
  )) {
    for (const family of requiredFamilies) {
      const groupId = `${topic.id}:${family}`;
      const publishers = new Set(
        catalog.placements
          .filter((placement) => placement.comparisonGroupId === groupId)
          .map((placement) => placement.publisher),
      );
      assert.ok(publishers.has('ZNews'), `${groupId} missing ZNews`);
      assert.ok(publishers.has('BaoMoi'), `${groupId} missing BaoMoi`);
    }
  }
});

test('all 46 category mastheads are retained as retired historical inventory', async () => {
  const catalog = buildZonesCatalog(await workbookRows());
  const mastheads = catalog.placements.filter(
    (placement) => placement.placementFamily === 'category_masthead',
  );

  assert.equal(mastheads.length, 46);
  assert.ok(mastheads.every((placement) => placement.lifecycleStatus === 'retired'));
  assert.ok(mastheads.some((placement) => placement.publisher === 'ZNews'));
  assert.ok(mastheads.some((placement) => placement.publisher === 'BaoMoi'));
});

test('Zone schema retains NP-6 fields when persisted', async () => {
  const source = buildZonesCatalog(await workbookRows());
  const document = new ZoneCatalog(source);
  const persisted = document.toObject();
  const sample = persisted.placements.find(
    (placement) => placement.id === 'Znews_FamilyParenting_Masthead',
  );

  assert.equal(persisted.catalogVersion, 'np6-2026-04');
  assert.equal(persisted.topicTaxonomy.length, 25);
  assert.equal(sample.topicId, 'family_parenting');
  assert.equal(sample.renderer.templateId, 'znews-static-category-v3');
  assert.equal(sample.audienceContext.taxonomyVersion, 'placement-topics-v2');
  assert.equal(sample.siteUrl, 'https://znews-stg.pawgrammers.io.vn/gia-dinh.html');
  assert.equal(sample.creativeContractId, 'znews-category-masthead-v1');
  assert.equal(sample.lifecycleStatus, 'retired');
});

test('Campaign schema retains the placement catalog snapshot', () => {
  const campaign = new Campaign({
    orderId: 'ORD-2026-999',
    brand: 'NP-6 Test',
    placements: ['Znews_FamilyParenting_Masthead'],
    catalogVersion: 'np6-2026-02',
    placementSnapshots: [{
      id: 'Znews_FamilyParenting_Masthead',
      topicId: 'family_parenting',
      creativeContractId: 'znews-category-masthead-v1',
      cpm: 65000,
    }],
  }).toObject();

  assert.equal(campaign.catalogVersion, 'np6-2026-02');
  assert.equal(campaign.placementSnapshots[0].topicId, 'family_parenting');
  assert.equal(
    campaign.placementSnapshots[0].creativeContractId,
    'znews-category-masthead-v1',
  );
});
