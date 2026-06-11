/**
 * Block 5 — Seed Script (v2)
 * Source of truth: Ads Zone.xlsx + Audience Library.xlsx
 *
 * Populates:
 *   - zones          (ZoneCatalog)   — 26 official + 14 test-site zones
 *   - audience_library (AudienceLibrary) — 310 segments from Excel
 *   - campaigns      (Campaign)      — 3 seed orders from mock
 *   - analytics_records (AnalyticsRecord) — 30-day generated data
 *
 * Usage:
 *   node seed/index.js           — skip collections that already have data
 *   node seed/index.js --force   — wipe and re-seed everything
 */
require('dotenv').config();
const path     = require('path');
const mongoose = require('mongoose');
const xlsx     = require('xlsx');

const ZoneCatalog      = require('../models/Zone');
const Campaign         = require('../models/Campaign');
const AnalyticsRecord  = require('../models/AnalyticsRecord');
const AudienceLibrary  = require('../models/AudienceLibrary');

// ─────────────────────────────────────────────────────────────────────────────
// READ EXCEL FILES
// ─────────────────────────────────────────────────────────────────────────────
const ZONE_FILE     = 'C:\\Users\\LENOVO\\Downloads\\Ads Zone.xlsx';
const AUDIENCE_FILE = 'C:\\Users\\LENOVO\\Downloads\\Audience Library.xlsx';

function readZonesFromExcel() {
  const wb   = xlsx.readFile(ZONE_FILE);
  const rows = xlsx.utils.sheet_to_json(wb.Sheets['Ad Zones'], { defval: null });
  return rows.map((r) => ({
    id:      r['Zone ID'],
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

function readAudienceFromExcel() {
  const wb   = xlsx.readFile(AUDIENCE_FILE);
  const rows = xlsx.utils.sheet_to_json(wb.Sheets['Sheet1'], { defval: null });
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
// BUILD ZONES CATALOG
// Derives groups & channels from zone rows + adds test-site zones
// ─────────────────────────────────────────────────────────────────────────────
function buildZonesCatalog(zoneRows) {
  // Groups from Excel (unique by Group column)
  const groupMap = {};
  for (const r of zoneRows) {
    if (!groupMap[r.channel]) groupMap[r.channel] = r.id.split('.')[0]; // rough group
  }

  // Official group definitions (match mock exactly)
  const groups = [
    { id: 'pulse-news',  name: 'PulseNews',      desc: 'News portal (web + app + WAP)',                       channels: ['pulse-news-app','pulse-news-wap','pulse-news-pr','pulse-news-pr-wap'] },
    { id: 'vibe-tv',     name: 'VibeTV Studio',  desc: 'Short video & livestream',                            channels: ['vibe-tv-web','vibe-tv-app','vibe-tv-onsocial'] },
    { id: 'wave-news',   name: 'WaveNews',        desc: 'Lifestyle & entertainment news',                      channels: ['wave-news-wap','wave-news-web'] },
    { id: 'play-verse',  name: 'PlayVerse',       desc: 'Gaming portal',                                      channels: ['play-verse-web'] },
    { id: 'stream-wave', name: 'StreamWave',      desc: 'Music & podcast',                                    channels: ['stream-wave-app'] },
    { id: 'message-app', name: 'MessageApp',      desc: 'Messaging super-app (chat, feed, story, mini-app)',  channels: ['message-app'] },
    // Test sites (Phase 1 from zone_mapping.md)
    { id: 'znews-site',  name: 'Znews (Test)',    desc: 'Real Znews replicate — stg.pawgrammers.io.vn',        channels: ['znews-site'] },
    { id: 'baomoi-site', name: 'BaoMoi (Test)',   desc: 'Real BaoMoi replicate — stg.pawgrammers.io.vn',       channels: ['baomoi-site'] },
    { id: 'zingmp3-site',name: 'ZingMP3 (Test)',  desc: 'Real ZingMP3 replicate — stg.pawgrammers.io.vn',      channels: ['zingmp3-site'] },
  ];

  const channels = {
    'pulse-news-app':    { name: 'PulseNews App',     reach: 4200000  },
    'pulse-news-wap':    { name: 'PulseNews Wap',     reach: 6800000  },
    'pulse-news-pr':     { name: 'PulseNews PR',      reach:  980000  },
    'pulse-news-pr-wap': { name: 'PulseNews PR_Wap',  reach: 1400000  },
    'vibe-tv-web':       { name: 'VibeTV Web',        reach: 3100000  },
    'vibe-tv-app':       { name: 'VibeTV App',        reach: 5500000  },
    'vibe-tv-onsocial':  { name: 'VibeTV onSocial',   reach: 2300000  },
    'wave-news-wap':     { name: 'WaveNews Wap',      reach: 2900000  },
    'wave-news-web':     { name: 'WaveNews Web',      reach: 1600000  },
    'play-verse-web':    { name: 'PlayVerse Web',     reach: 1200000  },
    'stream-wave-app':   { name: 'StreamWave App',    reach: 1850000  },
    'message-app':       { name: 'MessageApp',        reach: 52000000 },
    'znews-site':        { name: 'Znews Replicate',   reach: 1000000  },
    'baomoi-site':       { name: 'BaoMoi Replicate',  reach:  800000  },
    'zingmp3-site':      { name: 'ZingMP3 Replicate', reach:  500000  },
  };

  // Official placements from Excel (26 zones)
  const placements = zoneRows;

  // Test-site zones (Phase 1 — from zone_mapping.md analysis)
  const testSiteZones = [
    { id: 'ZingNews_Masthead',          channel: 'znews-site',  format: 'banner', size: '1160x250', reach: 600000, vi: 72, ctr: 0.65, cpm: 20000, obj: 'awareness',     testSiteZone: 'ZingNews_Masthead',          siteId: 'znews' },
    { id: 'ZingNews_Halfpage',          channel: 'znews-site',  format: 'banner', size: '300x600',  reach: 420000, vi: 65, ctr: 0.55, cpm: 18000, obj: 'consideration', testSiteZone: 'ZingNews_Halfpage',          siteId: 'znews' },
    { id: 'ZingNews_PrBox_2',           channel: 'znews-site',  format: 'banner', size: '300x250',  reach: 380000, vi: 60, ctr: 0.50, cpm: 15000, obj: 'conversion',    testSiteZone: 'ZingNews_PrBox_2',           siteId: 'znews' },
    { id: 'ZingNews_Masthead_Inline_1', channel: 'znews-site',  format: 'banner', size: '970x250',  reach: 500000, vi: 68, ctr: 0.60, cpm: 19000, obj: 'consideration', testSiteZone: 'ZingNews_Masthead_Inline_1', siteId: 'znews' },
    { id: 'ZingNews_Background',        channel: 'znews-site',  format: 'banner', size: 'skin',     reach: 600000, vi: 55, ctr: 0.30, cpm: 25000, obj: 'awareness',     testSiteZone: 'ZingNews_Background',        siteId: 'znews' },
    { id: 'ZingNews_SideLeft',          channel: 'znews-site',  format: 'banner', size: 'skin',     reach: 600000, vi: 50, ctr: 0.28, cpm: 12000, obj: 'awareness',     testSiteZone: 'ZingNews_SideLeft',          siteId: 'znews' },
    { id: 'ZingNews_SideRight',         channel: 'znews-site',  format: 'banner', size: 'skin',     reach: 600000, vi: 50, ctr: 0.28, cpm: 12000, obj: 'awareness',     testSiteZone: 'ZingNews_SideRight',         siteId: 'znews' },
    { id: 'BaoMoi_Masthead',            channel: 'baomoi-site', format: 'banner', size: '1160x280', reach: 480000, vi: 70, ctr: 0.62, cpm: 19000, obj: 'awareness',     testSiteZone: 'BaoMoi_Masthead',            siteId: 'baomoi' },
    { id: 'BaoMoi_Box1',                channel: 'baomoi-site', format: 'banner', size: '300x250',  reach: 360000, vi: 62, ctr: 0.52, cpm: 14000, obj: 'conversion',    testSiteZone: 'BaoMoi_Box1',                siteId: 'baomoi' },
    { id: 'BaoMoi_Box2',                channel: 'baomoi-site', format: 'banner', size: '300x600',  reach: 320000, vi: 64, ctr: 0.56, cpm: 16000, obj: 'consideration', testSiteZone: 'BaoMoi_Box2',                siteId: 'baomoi' },
    { id: 'BaoMoi_Background',          channel: 'baomoi-site', format: 'banner', size: 'skin',     reach: 480000, vi: 55, ctr: 0.30, cpm: 23000, obj: 'awareness',     testSiteZone: 'BaoMoi_Background',          siteId: 'baomoi' },
    { id: 'BaoMoi_StickyLeft',          channel: 'baomoi-site', format: 'banner', size: 'skin',     reach: 480000, vi: 50, ctr: 0.28, cpm: 11000, obj: 'awareness',     testSiteZone: 'BaoMoi_StickyLeft',          siteId: 'baomoi' },
    { id: 'BaoMoi_StickyRight',         channel: 'baomoi-site', format: 'banner', size: 'skin',     reach: 480000, vi: 50, ctr: 0.28, cpm: 11000, obj: 'awareness',     testSiteZone: 'BaoMoi_StickyRight',         siteId: 'baomoi' },
    { id: 'ZingMP3_Masthead',           channel: 'zingmp3-site',format: 'banner', size: '1200x250', reach: 300000, vi: 68, ctr: 0.45, cpm: 17000, obj: 'awareness',     testSiteZone: 'ZingMP3_Masthead',           siteId: 'zingmp3' },
  ];

  return { groups, channels, placements: [...placements, ...testSiteZones] };
}

// ─────────────────────────────────────────────────────────────────────────────
// SEED: CAMPAIGNS (from mock — no Excel source for these)
// ─────────────────────────────────────────────────────────────────────────────
const CAMPAIGNS_SEED = [
  {
    orderId: 'ORD-2026-001', brand: 'Brand A', advertiser: 'BrandA Vietnam',
    objective: 'awareness', status: 'active',
    budget: 425000000, daily: 43000000, rate: 36960, rateType: 'CPM',
    startDate: '2026-05-10', endDate: '2026-06-07',
    creative: { name: 'Mazda CX-5 Inpage 16/5', size: '720x1280', url: '' },
    placements: ['PulseNews.Home.Inpage1','PulseNews.Sub.Inpage','VibeTV.ShortVideo.Infeed.Fullscreen1'],
    targeting: { geo: ['Hà Nội','TP.HCM','Đà Nẵng'], age: ['25-34','35-44'], gender: [], deviceOS: ['Android','iOS'], marital: [], parental: [], education: [], income: ['Top 5-10%','Top 10-25%'], career: [], interest: [], weather: [] },
    dmp: { include: ['INT056','INT004'], exclude: [] }, // Automotive, Aviation
    warnings: ['Zone "PulseNews.Home.Inpage1" expects 728x90 banner, but creative size is 720x1280.'],
  },
  {
    orderId: 'ORD-2026-002', brand: 'FlyDragon Airlines', advertiser: 'FlyDragon JSC',
    objective: 'conversion', status: 'paused',
    budget: 280000000, daily: 25000000, rate: 42000, rateType: 'CPM',
    startDate: '2026-05-15', endDate: '2026-06-15',
    creative: { name: 'FlyDragon Summer Sale', size: '1080x1080', url: '' },
    placements: ['VibeTV.ShortVideo.Infeed.Fullscreen2','WaveNews.Home.Inpage1'],
    targeting: { geo: ['Hà Nội','TP.HCM'], age: ['25-34','35-44','45-54'], gender: [], deviceOS: ['Android','iOS'], marital: [], parental: [], education: [], income: ['Top 5%','Top 5-10%'], career: [], interest: [], weather: [] },
    dmp: { include: ['BEH001','INT004'], exclude: [] }, // Travel, Aviation
    warnings: ['Zone "VibeTV.ShortVideo.Infeed.Fullscreen2" expects 1080x1920 video-vertical, but creative size is 1080x1080.'],
  },
  {
    orderId: 'ORD-2026-003', brand: 'NeoCard Finance', advertiser: 'NeoCard Vietnam',
    objective: 'consideration', status: 'pending',
    budget: 180000000, daily: 18000000, rate: 38500, rateType: 'CPM',
    startDate: '2026-06-01', endDate: '2026-06-30',
    creative: { name: 'NeoCard Cashback Launch', size: '320x480', url: '' },
    placements: ['PulseNews.Cate.Inpage1','WaveNews.Inpage2'],
    targeting: { geo: ['TP.HCM','Hà Nội'], age: ['25-34'], gender: ['Male'], deviceOS: ['iOS'], marital: [], parental: [], education: ['College & Bachelor','Master'], income: ['Top 10-25%'], career: ['Office Worker'], interest: [], weather: [] },
    dmp: { include: ['INT021','INT022'], exclude: [] }, // Banking, Credit cards
    warnings: ['Zone "PulseNews.Cate.Inpage1" expects 300x250 banner, but creative size is 320x480.'],
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// ANALYTICS GENERATOR (realistic 30-day data)
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

        const noise        = () => 0.7 + Math.random() * 0.6;
        const baseImp      = Math.round((campaign.daily / placement.cpm) * 1000 * noise());
        const impressions  = Math.max(100, baseImp);
        const ctr          = parseFloat((placement.ctr * noise()).toFixed(3));
        const clicks       = Math.round(impressions * (ctr / 100));
        const vi           = parseFloat((placement.vi * (0.9 + Math.random() * 0.2)).toFixed(1));
        const cpm          = Math.round(placement.cpm * noise());
        const spend        = Math.round((impressions / 1000) * cpm);
        const conversions  = campaign.objective === 'conversion'
          ? Math.round(clicks * (0.02 + Math.random() * 0.04))
          : Math.round(clicks * (0.005 + Math.random() * 0.01));
        const reach        = Math.round(impressions * (0.7 + Math.random() * 0.25));

        records.push({ campaignId: campaign.orderId, placementId, date: dateStr, channel: placement.channel, format: placement.format, impressions, clicks, spend, ctr, cpm, vi, reach, conversions });
      }
    }
  }
  return records;
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN
// ─────────────────────────────────────────────────────────────────────────────
async function runSeed(opts = {}) {
  const force = opts.force || process.argv.includes('--force');

  // ── Read Excel files ────────────────────────────────────────────────────────
  console.log('  📂  Reading Excel files...');
  const zoneRows    = readZonesFromExcel();
  const audRows     = readAudienceFromExcel();
  const zonesCatalog = buildZonesCatalog(zoneRows);
  console.log(`       Zones from Excel: ${zoneRows.length} official + ${zonesCatalog.placements.length - zoneRows.length} test-site`);
  console.log(`       Audience segments: ${audRows.length}`);

  // ── Zones ───────────────────────────────────────────────────────────────────
  if (!opts.skipZones) {
    const count = await ZoneCatalog.countDocuments();
    if (count && !force) {
      console.log('  ⏭  Zones already seeded — skip (--force to overwrite)');
    } else {
      await ZoneCatalog.deleteMany({});
      await ZoneCatalog.create(zonesCatalog);
      console.log(`  ✅  Zones seeded: ${zonesCatalog.groups.length} groups, ${Object.keys(zonesCatalog.channels).length} channels, ${zonesCatalog.placements.length} placements`);
    }
  }

  // ── Audience Library ────────────────────────────────────────────────────────
  const audCount = await AudienceLibrary.countDocuments();
  if (audCount && !force) {
    console.log(`  ⏭  Audience Library already seeded (${audCount} segments) — skip`);
  } else {
    await AudienceLibrary.deleteMany({});
    await AudienceLibrary.insertMany(audRows);
    console.log(`  ✅  Audience Library seeded: ${audRows.length} segments`);
  }

  // ── Campaigns ───────────────────────────────────────────────────────────────
  const campCount = await Campaign.countDocuments();
  if (campCount && !force) {
    console.log(`  ⏭  Campaigns already seeded (${campCount} orders) — skip`);
  } else {
    await Campaign.deleteMany({});
    await Campaign.insertMany(CAMPAIGNS_SEED);
    console.log(`  ✅  Campaigns seeded: ${CAMPAIGNS_SEED.length} orders`);
  }

  // ── Analytics ───────────────────────────────────────────────────────────────
  const analyticsCount = await AnalyticsRecord.countDocuments();
  if (analyticsCount && !force) {
    console.log(`  ⏭  Analytics already seeded (${analyticsCount} records) — skip`);
  } else {
    await AnalyticsRecord.deleteMany({});
    const rows = generateAnalytics(CAMPAIGNS_SEED, zonesCatalog.placements);
    await AnalyticsRecord.insertMany(rows);
    console.log(`  ✅  Analytics seeded: ${rows.length} daily records`);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CLI
// ─────────────────────────────────────────────────────────────────────────────
if (require.main === module) {
  const URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/adspilot';
  console.log(`\n🌱  AdsPilot Seed Script v2`);
  console.log(`    DB  : ${URI}`);
  console.log(`    Mode: ${process.argv.includes('--force') ? 'FORCE (wipe + re-seed)' : 'safe (skip existing)'}\n`);

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
