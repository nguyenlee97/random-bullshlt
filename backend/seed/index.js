/**
 * Block 5 — Seed Script (v3)
 * Source of truth: seed/data/Ads Zone.xlsx + seed/data/Audience Library.xlsx
 *
 * Strategy (E1 Zone Refinement):
 *   - 26 mock zones are FORCED-MAPPED to real test-site zone IDs.
 *     Performance metrics (Reach/VI/CTR/CPM/Objective) kept from mock data.
 *     Format/size/channel changed to match real ad slots.
 *   - 12 unmapped real zone slots (category side strips) added as catalog-only entries.
 *   - Audio/video formats converted to banner/skin.
 *   - Total: 38 placements (26 mock-mapped + 12 real-only)
 *
 * Usage:
 *   node seed/index.js              — skip collections that already have data
 *   node seed/index.js --force      — wipe + re-seed everything
 *   node seed/index.js --zones-only — seed only zones+campaigns (skip analytics)
 */
require('dotenv').config();
const path     = require('path');
const mongoose = require('mongoose');
const { readWorksheetRows } = require('./workbook-rows');

const ZoneCatalog      = require('../models/Zone');
const Campaign         = require('../models/Campaign');
const AnalyticsRecord  = require('../models/AnalyticsRecord');
const AudienceLibrary  = require('../models/AudienceLibrary');

// ─────────────────────────────────────────────────────────────────────────────
// READ EXCEL FILES — relative paths (works on any OS)
// ─────────────────────────────────────────────────────────────────────────────
const ZONE_FILE     = path.join(__dirname, 'data', 'Ads Zone.xlsx');
const AUDIENCE_FILE = path.join(__dirname, 'data', 'Audience Library.xlsx');

async function readZonesFromExcel() {
  const rows = await readWorksheetRows(ZONE_FILE, 'Ad Zones');
  return rows.map((r) => ({
    mockId:  r['Zone ID'],
    channel: r['Channel'],
    format:  r['Format'],
    size:    r['Size'],
    reach:   r['Reach']     || 0,
    vi:      r['VI %']      || 0,
    ctr:     r['CTR %']     || 0,
    cpm:     r['CPM VND']   || 0,
    obj:     (r['Objective'] || '').toLowerCase(),
    note:    r['Note']      || null,
  }));
}

async function readAudienceFromExcel() {
  const rows = await readWorksheetRows(AUDIENCE_FILE, 'Sheet1');
  return rows.map((r) => ({
    segmentId:   r['ID'],
    type:        r['Type'],
    category:    r['Category']    || '',
    subcategory: r['Subcategory'] || null,
    name:        r['Name'],
    context:     r['Context']     || null,
    fullLabel:   r['Full Label']  || r['Name'],
    sizeMin:     r['Size Min']    || null,
    sizeMax:     r['Size Max']    || null,
    sizeRaw:     r['Size (raw)']  || null,
  }));
}

// ─────────────────────────────────────────────────────────────────────────────
// E1 FORCED MAPPING: mock zone ID → real zone ID + overrides
// Keys are mock zone IDs from Excel.
// Values define the real zone to use, overriding format/size/channel.
// Performance metrics (reach/vi/ctr/cpm/obj) are kept from the mock data.
// ─────────────────────────────────────────────────────────────────────────────
const FORCED_ZONE_MAP = {
  // ── PulseNews zones → Znews home + category ──────────────────────────────
  'PulseNews.Cate.Inpage1':    { id: 'ZingNews_PrBox_2',            format: 'banner', size: '300x600',  channel: 'znews-site',        siteId: 'znews' },
  'PulseNews.Cate.Inpage2':    { id: 'Znews_KinhDoanh_SidebarBox',  format: 'banner', size: '300x250',  channel: 'znews-kinh-doanh',  siteId: 'znews',  flexible: true },
  'PulseNews.Home.Inpage1':    { id: 'ZingNews_Masthead',            format: 'banner', size: '1160x250', channel: 'znews-site',        siteId: 'znews' },
  'PulseNews.Home.Inpage2':    { id: 'ZingNews_Halfpage',            format: 'banner', size: '300x600',  channel: 'znews-site',        siteId: 'znews' },
  'PulseNews.Sub.Inpage':      { id: 'Znews_DoiSong_SidebarBox',    format: 'banner', size: '300x250',  channel: 'znews-doi-song',    siteId: 'znews',  flexible: true },

  // ── WaveNews zones → Znews inline + BaoMoi ───────────────────────────────
  'WaveNews.Inpage1':          { id: 'BaoMoi_Box1',                  format: 'banner', size: '300x250',  channel: 'baomoi-site',       siteId: 'baomoi' },
  'WaveNews.Inpage2':          { id: 'BaoMoi_Box2',                  format: 'banner', size: '300x600',  channel: 'baomoi-site',       siteId: 'baomoi' },
  'WaveNews.Home.Inpage1':     { id: 'ZingNews_Masthead_Inline_1',   format: 'banner', size: '1160x250', channel: 'znews-site',        siteId: 'znews' },

  // ── VibeTV (video → skin/banner) ─────────────────────────────────────────
  'VibeTV.ShortVideo.Infeed.Fullscreen1': { id: 'Znews_CongNghe_Background', format: 'skin', size: 'skin', channel: 'znews-cong-nghe', siteId: 'znews' },
  'VibeTV.ShortVideo.Infeed.Fullscreen2': { id: 'Znews_TheThao_Background',  format: 'skin', size: 'skin', channel: 'znews-the-thao',  siteId: 'znews' },
  'VibeTV.ShortVideo.Infeed.Fullscreen3': { id: 'Znews_GiaiTri_Background',  format: 'skin', size: 'skin', channel: 'znews-giai-tri',  siteId: 'znews' },
  'VibeTV.ShortVideo.Infeed.Fullscreen4': { id: 'Znews_DoiSong_Background',  format: 'skin', size: 'skin', channel: 'znews-doi-song',  siteId: 'znews' },
  'VibeTV.ShortVideo.Infeed.Fullscreen5': { id: 'Znews_SucKhoe_Background',  format: 'skin', size: 'skin', channel: 'znews-suc-khoe',  siteId: 'znews' },

  // ── PlayVerse → Znews Tech category ──────────────────────────────────────
  'PlayVerse.Banner.Home':     { id: 'Znews_CongNghe_SidebarBox',   format: 'banner', size: '300x250',  channel: 'znews-cong-nghe',   siteId: 'znews',  flexible: true },

  // ── StreamWave (audio → skin) ─────────────────────────────────────────────
  'StreamWave.AudioAd.Mid':    { id: 'Znews_KinhDoanh_Background',  format: 'skin',   size: 'skin',     channel: 'znews-kinh-doanh',  siteId: 'znews' },

  // ── MessageApp (various → banner/skin) ───────────────────────────────────
  'MessageApp.Inbox.Banner':      { id: 'BaoMoi_Masthead',           format: 'banner', size: '1160x280', channel: 'baomoi-site',       siteId: 'baomoi' },
  'MessageApp.Inbox.Native':      { id: 'BaoMoi_Background',         format: 'skin',   size: 'skin',     channel: 'baomoi-site',       siteId: 'baomoi', subFormat: 'background' },
  'MessageApp.Feed.Carousel':     { id: 'BaoMoi_StickyLeft',         format: 'skin',   size: 'skin',     channel: 'baomoi-site',       siteId: 'baomoi', subFormat: 'side-left' },
  'MessageApp.Story.Fullscreen':  { id: 'BaoMoi_StickyRight',        format: 'skin',   size: 'skin',     channel: 'baomoi-site',       siteId: 'baomoi', subFormat: 'side-right' },
  'MessageApp.Story.Video':       { id: 'Znews_TheThao_SidebarBox',  format: 'banner', size: '300x250',  channel: 'znews-the-thao',    siteId: 'znews',  flexible: true },
  'MessageApp.InApp.Interstitial':{ id: 'Znews_GiaiTri_SidebarBox',  format: 'banner', size: '300x250',  channel: 'znews-giai-tri',    siteId: 'znews',  flexible: true },
  'MessageApp.InApp.MREC':        { id: 'Znews_SucKhoe_SidebarBox',  format: 'banner', size: '300x250',  channel: 'znews-suc-khoe',    siteId: 'znews',  flexible: true },
  'MessageApp.InApp.RewardVideo': { id: 'ZingMP3_Masthead',          format: 'banner', size: '2032x528', channel: 'zingmp3-site',      siteId: 'zingmp3' },
};

// ─────────────────────────────────────────────────────────────────────────────
// CHANNEL → TEST SITE URL
// Maps each channel key (used in FORCED_ZONE_MAP) to the exact page URL on the
// staging test site where that ad slot appears.
// ─────────────────────────────────────────────────────────────────────────────
const CHANNEL_SITE_URLS = {
  'znews-site':       'https://znews-stg.pawgrammers.io.vn/',
  'znews-kinh-doanh': 'https://znews-stg.pawgrammers.io.vn/kinh-doanh.html',
  'znews-suc-khoe':   'https://znews-stg.pawgrammers.io.vn/suc-khoe.html',
  'znews-the-thao':   'https://znews-stg.pawgrammers.io.vn/the-thao.html',
  'znews-doi-song':   'https://znews-stg.pawgrammers.io.vn/doi-song.html',
  'znews-cong-nghe':  'https://znews-stg.pawgrammers.io.vn/cong-nghe.html',
  'znews-giai-tri':   'https://znews-stg.pawgrammers.io.vn/giai-tri.html',
  'baomoi-site':      'https://baomoi-stg.pawgrammers.io.vn/',
  'zingmp3-site':     'https://zingmp3-stg.pawgrammers.io.vn/',
};

// ─────────────────────────────────────────────────────────────────────────────
function buildZonesCatalog(mockRows) {
  const groups = [
    // Real test-site groups only
    { id: 'znews-site',       name: 'ZNews Home',        desc: 'Znews homepage — znews-stg.pawgrammers.io.vn',              channels: ['znews-site'] },
    { id: 'znews-categories', name: 'ZNews Categories',  desc: 'Znews category pages (Tech, Sport, Business, etc.)',        channels: ['znews-cong-nghe','znews-the-thao','znews-giai-tri','znews-doi-song','znews-suc-khoe','znews-kinh-doanh'] },
    { id: 'baomoi-site',      name: 'BaoMoi',            desc: 'BaoMoi homepage — baomoi-stg.pawgrammers.io.vn',            channels: ['baomoi-site'] },
    { id: 'zingmp3-site',     name: 'ZingMP3',           desc: 'ZingMP3 homepage — zingmp3-stg.pawgrammers.io.vn',          channels: ['zingmp3-site'] },
  ];

  const channels = {
    // Znews channels
    'znews-site':        { name: 'Znews Home',       reach: 1000000 },
    'znews-cong-nghe':   { name: 'Znews Tech',       reach:  420000 },
    'znews-doi-song':    { name: 'Znews Lifestyle',  reach:  380000 },
    'znews-giai-tri':    { name: 'Znews Entertainment', reach: 460000 },
    'znews-kinh-doanh':  { name: 'Znews Business',   reach:  350000 },
    'znews-suc-khoe':    { name: 'Znews Health',     reach:  310000 },
    'znews-the-thao':    { name: 'Znews Sports',     reach:  500000 },
    // BaoMoi channels
    'baomoi-site':       { name: 'BaoMoi',           reach:  800000 },
    // ZingMP3 channel
    'zingmp3-site':      { name: 'ZingMP3',          reach:  500000 },
  };

  // ── Build placements: apply forced mapping to mock rows ──────────────────
  const mappedPlacements = mockRows.map((row) => {
    const override = FORCED_ZONE_MAP[row.mockId];
    if (!override) {
      console.warn(`  ⚠️  No forced mapping for mock zone: ${row.mockId} — skipping`);
      return null;
    }
    return {
      id:       override.id,
      mockId:   row.mockId,          // original mock zone ID for reference
      channel:  override.channel,
      format:   override.format,
      size:     override.size,
      reach:    row.reach,
      vi:       row.vi,
      ctr:      row.ctr,
      cpm:      row.cpm,
      obj:      row.obj,
      note:     row.note,
      siteId:   override.siteId,
      testSiteZone: override.id,
      siteUrl:  CHANNEL_SITE_URLS[override.channel] || null,
    };
  }).filter(Boolean);

  // ── 12 unmapped real zone slots (category side strips, no mock counterpart) ─
  const CATE_SIDE_STRIPS = [
    'CongNghe','TheThao','GiaiTri','DoiSong','SucKhoe','KinhDoanh',
  ].flatMap((cat) => {
    const channelId = `znews-${cat.toLowerCase().replace('congnghe','cong-nghe').replace('theThao','the-thao').replace('giaitri','giai-tri').replace('doisong','doi-song').replace('suckhoe','suc-khoe').replace('kinhdoanh','kinh-doanh')}`;
    // map category name to channel id properly
    const chanMap = {
      CongNghe:  'znews-cong-nghe',
      TheThao:   'znews-the-thao',
      GiaiTri:   'znews-giai-tri',
      DoiSong:   'znews-doi-song',
      SucKhoe:   'znews-suc-khoe',
      KinhDoanh: 'znews-kinh-doanh',
    };
    const ch = chanMap[cat];
    return [
      { id: `Znews_${cat}_SideLeft`,  channel: ch, format: 'skin', size: 'skin', subFormat: 'side-left',  reach: 200000, vi: 45, ctr: 0.25, cpm: 10000, obj: 'awareness', siteId: 'znews', testSiteZone: `Znews_${cat}_SideLeft`,  siteUrl: CHANNEL_SITE_URLS[ch] || null },
      { id: `Znews_${cat}_SideRight`, channel: ch, format: 'skin', size: 'skin', subFormat: 'side-right', reach: 200000, vi: 45, ctr: 0.25, cpm: 10000, obj: 'awareness', siteId: 'znews', testSiteZone: `Znews_${cat}_SideRight`, siteUrl: CHANNEL_SITE_URLS[ch] || null },
    ];
  });

  const placements = [...mappedPlacements, ...CATE_SIDE_STRIPS];

  return { groups, channels, placements };
}

// ─────────────────────────────────────────────────────────────────────────────
// SEED CAMPAIGNS (updated to use real zone IDs)
// ─────────────────────────────────────────────────────────────────────────────
const CAMPAIGNS_SEED = [
  {
    orderId: 'ORD-2026-001', brand: 'Brand A', advertiser: 'BrandA Vietnam',
    objective: 'awareness', status: 'active',
    budget: 425000000, daily: 43000000, rate: 36960, rateType: 'CPM',
    startDate: '2026-05-10', endDate: '2026-07-07',
    creative: { name: 'Mazda CX-5 Inpage', size: '1160x250', url: '' },
    placements: ['ZingNews_Masthead', 'Znews_CongNghe_Background'],
    targeting: { geo: ['Hà Nội','TP.HCM','Đà Nẵng'], age: ['25-34','35-44'], gender: [], deviceOS: ['Android','iOS'], marital: [], parental: [], education: [], income: ['Top 5-10%','Top 10-25%'], career: [], interest: [], weather: [] },
    dmp: { include: ['INT056','INT004'], exclude: [] },
    warnings: [],
  },
  {
    orderId: 'ORD-2026-002', brand: 'FlyDragon Airlines', advertiser: 'FlyDragon JSC',
    objective: 'conversion', status: 'paused',
    budget: 280000000, daily: 25000000, rate: 42000, rateType: 'CPM',
    startDate: '2026-05-15', endDate: '2026-07-15',
    creative: { name: 'FlyDragon Summer Sale', size: '1160x250', url: '' },
    placements: ['ZingNews_Masthead_Inline_1', 'BaoMoi_Masthead'],
    targeting: { geo: ['Hà Nội','TP.HCM'], age: ['25-34','35-44','45-54'], gender: [], deviceOS: ['Android','iOS'], marital: [], parental: [], education: [], income: ['Top 5%','Top 5-10%'], career: [], interest: [], weather: [] },
    dmp: { include: ['BEH001','INT004'], exclude: [] },
    warnings: [],
  },
  {
    orderId: 'ORD-2026-003', brand: 'NeoCard Finance', advertiser: 'NeoCard Vietnam',
    objective: 'consideration', status: 'pending',
    budget: 180000000, daily: 18000000, rate: 38500, rateType: 'CPM',
    startDate: '2026-06-01', endDate: '2026-07-30',
    creative: { name: 'NeoCard Cashback Launch', size: '300x250', url: '' },
    placements: ['ZingNews_PrBox_2', 'BaoMoi_Box1'],
    targeting: { geo: ['TP.HCM','Hà Nội'], age: ['25-34'], gender: ['Male'], deviceOS: ['iOS'], marital: [], parental: [], education: ['College & Bachelor','Master'], income: ['Top 10-25%'], career: ['Office Worker'], interest: [], weather: [] },
    dmp: { include: ['INT021','INT022'], exclude: [] },
    warnings: [],
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// ANALYTICS GENERATOR
// ─────────────────────────────────────────────────────────────────────────────
function generateAnalytics(campaigns, placements) {
  const records = [];
  const today   = new Date();

  for (const campaign of campaigns) {
    for (const placementId of campaign.placements) {
      const placement = placements.find((p) => p.id === placementId);
      if (!placement) continue;

      for (let d = 29; d >= 0; d--) {
        const date = new Date(today);
        date.setDate(date.getDate() - d);
        const dateStr = date.toISOString().slice(0, 10);

        if (dateStr < campaign.startDate || dateStr > campaign.endDate) continue;

        const noise       = () => 0.7 + Math.random() * 0.6;
        const baseImp     = Math.round((campaign.daily / placement.cpm) * 1000 * noise());
        const impressions = Math.max(100, baseImp);
        const ctr         = parseFloat((placement.ctr * noise()).toFixed(3));
        const clicks      = Math.round(impressions * (ctr / 100));
        const vi          = parseFloat((placement.vi * (0.9 + Math.random() * 0.2)).toFixed(1));
        const cpm         = Math.round(placement.cpm * noise());
        const spend       = Math.round((impressions / 1000) * cpm);
        const conversions = campaign.objective === 'conversion'
          ? Math.round(clicks * (0.02 + Math.random() * 0.04))
          : Math.round(clicks * (0.005 + Math.random() * 0.01));
        const reach = Math.round(impressions * (0.7 + Math.random() * 0.25));

        records.push({
          campaignId:  campaign.orderId,
          placementId,
          date:        dateStr,
          channel:     placement.channel,
          format:      placement.format,
          impressions, clicks, spend, ctr, cpm, vi, reach, conversions,
        });
      }
    }
  }
  return records;
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN
// ─────────────────────────────────────────────────────────────────────────────
async function runSeed(opts = {}) {
  const force     = opts.force     || process.argv.includes('--force');
  const zonesOnly = opts.zonesOnly || process.argv.includes('--zones-only');

  // ── Read Excel files ───────────────────────────────────────────────────────
  console.log('  📂  Reading Excel files...');
  const mockRows    = await readZonesFromExcel();
  const audRows     = await readAudienceFromExcel();
  const zonesCatalog = buildZonesCatalog(mockRows);
  const { placements } = zonesCatalog;
  console.log(`       Mock zones read: ${mockRows.length}`);
  console.log(`       Mapped placements: ${placements.filter(p => p.mockId).length} (+ ${placements.filter(p => !p.mockId).length} real-only)`);
  console.log(`       Total placements: ${placements.length}`);
  console.log(`       Audience segments: ${audRows.length}`);

  // ── Zones ──────────────────────────────────────────────────────────────────
  const zoneCount = await ZoneCatalog.countDocuments();
  if (zoneCount && !force) {
    console.log('  ⏭  Zones already seeded — skip (--force to overwrite)');
  } else {
    await ZoneCatalog.deleteMany({});
    await ZoneCatalog.create(zonesCatalog);
    console.log(`  ✅  Zones seeded: ${zonesCatalog.groups.length} groups, ${Object.keys(zonesCatalog.channels).length} channels, ${placements.length} placements`);
  }

  // ── Audience Library ───────────────────────────────────────────────────────
  const audCount = await AudienceLibrary.countDocuments();
  if (audCount && !force) {
    console.log(`  ⏭  Audience Library already seeded (${audCount} segments) — skip`);
  } else {
    await AudienceLibrary.deleteMany({});
    await AudienceLibrary.insertMany(audRows);
    console.log(`  ✅  Audience Library seeded: ${audRows.length} segments`);
  }

  // ── Campaigns ──────────────────────────────────────────────────────────────
  const campCount = await Campaign.countDocuments();
  if (campCount && !force) {
    console.log(`  ⏭  Campaigns already seeded (${campCount} orders) — skip`);
  } else {
    await Campaign.deleteMany({});
    await Campaign.insertMany(CAMPAIGNS_SEED);
    console.log(`  ✅  Campaigns seeded: ${CAMPAIGNS_SEED.length} orders`);
  }

  // ── Analytics (skip if --zones-only) ──────────────────────────────────────
  if (zonesOnly) {
    console.log('  ⏭  Analytics skipped (--zones-only mode)');
    return;
  }

  const analyticsCount = await AnalyticsRecord.countDocuments();
  if (analyticsCount && !force) {
    console.log(`  ⏭  Analytics already seeded (${analyticsCount} records) — skip`);
  } else {
    await AnalyticsRecord.deleteMany({});
    const rows = generateAnalytics(CAMPAIGNS_SEED, placements);
    await AnalyticsRecord.insertMany(rows);
    console.log(`  ✅  Analytics seeded: ${rows.length} daily records`);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CLI
// ─────────────────────────────────────────────────────────────────────────────
if (require.main === module) {
  const URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/adspilot';
  console.log(`\n🌱  AdsPilot Seed Script v3 (E1 Zone Refinement)`);
  console.log(`    DB  : ${URI}`);
  console.log(`    Mode: ${process.argv.includes('--force') ? 'FORCE (wipe + re-seed)' : 'safe (skip existing)'}`);
  console.log(`    Zones: ${process.argv.includes('--zones-only') ? 'zones+campaigns only' : 'full seed'}\n`);

  mongoose.connect(URI)
    .then(async () => {
      await runSeed();
      console.log('\n🎉  Seeding complete!\n');
      process.exit(0);
    })
    .catch((err) => {
      console.error('\n❌  Seed failed:', err.message);
      process.exit(1);
    });
}

module.exports = { runSeed };
