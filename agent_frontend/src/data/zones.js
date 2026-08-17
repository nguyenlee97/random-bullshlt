// ─── Zone catalog ─────────────────────────────────────────────────────────────
const LEGACY_BACKEND_URL = (
  import.meta.env.VITE_BACKEND_URL || 'https://api.pawgrammers.io.vn'
).replace(/\/$/, '')
const LEGACY_SITE_URLS = {
  ZingNews: import.meta.env.VITE_ZNEWS_URL || 'https://znews.pawgrammers.io.vn',
  BaoMoi: import.meta.env.VITE_BAOMOI_URL || 'https://baomoi.pawgrammers.io.vn',
  ZingMP3: import.meta.env.VITE_ZINGMP3_URL || 'https://zingmp3.pawgrammers.io.vn',
}
const legacyZoneUrl = id => `${LEGACY_BACKEND_URL}/api/zones?id=${encodeURIComponent(id)}`

const RAW_ZONES = [
  // ── MessageApp ──────────────────────────────────────────────────────────────
  { id: 'MSG.Story.Fullscreen', platform: 'MessageApp', placement: 'Story',    name: 'Story Fullscreen Image', format: 'Image',  size: '1080×1920', reach: 26, vi: 93, ctr: 0.70, cpm: 48000, objectives: ['awareness','consideration'], siteUrl: null,                                        adspilotUrl: legacyZoneUrl('MSG.Story.Fullscreen') },
  { id: 'MSG.Story.Video',      platform: 'MessageApp', placement: 'Story',    name: 'Story Fullscreen Video', format: 'Video',  size: '1080×1920', reach: 22, vi: 95, ctr: 0.62, cpm: 56000, objectives: ['awareness','consideration'], siteUrl: null,                                        adspilotUrl: legacyZoneUrl('MSG.Story.Video') },
  { id: 'MSG.InApp.Reward',     platform: 'MessageApp', placement: 'InApp',    name: 'Rewarded Video',         format: 'Video',  size: '1080×1920', reach: 14, vi: 97, ctr: 1.40, cpm: 60000, objectives: ['conversion'],                siteUrl: null,                                        adspilotUrl: legacyZoneUrl('MSG.InApp.Reward') },
  { id: 'MSG.Feed.Native1',     platform: 'MessageApp', placement: 'Feed',     name: 'Feed Native 1',          format: 'Native', size: '1200×628',  reach: 41, vi: 68, ctr: 1.45, cpm: 30000, objectives: ['consideration','conversion'], siteUrl: null,                                        adspilotUrl: legacyZoneUrl('MSG.Feed.Native1') },
  { id: 'MSG.Inbox.Banner',     platform: 'MessageApp', placement: 'Inbox',    name: 'Inbox Banner',           format: 'Banner', size: '1080×180',  reach: 38, vi: 74, ctr: 0.95, cpm: 17000, objectives: ['awareness'],                 siteUrl: null,                                        adspilotUrl: legacyZoneUrl('MSG.Inbox.Banner') },
  { id: 'MSG.Feed.Native2',     platform: 'MessageApp', placement: 'Feed',     name: 'Feed Native 2',          format: 'Native', size: '1200×628',  reach: 36, vi: 66, ctr: 1.30, cpm: 28000, objectives: ['consideration','conversion'], siteUrl: null,                                        adspilotUrl: legacyZoneUrl('MSG.Feed.Native2') },
  // ── ZingNews ────────────────────────────────────────────────────────────────
  { id: 'ZN.Masthead.Desktop',  platform: 'ZingNews',   placement: 'Masthead', name: 'Masthead Desktop',       format: 'Image',  size: '970×250',   reach: 18, vi: 85, ctr: 0.55, cpm: 42000, objectives: ['awareness'],                 siteUrl: LEGACY_SITE_URLS.ZingNews,  adspilotUrl: legacyZoneUrl('ZN.Masthead.Desktop') },
  { id: 'ZN.Masthead.Mobile',   platform: 'ZingNews',   placement: 'Masthead', name: 'Masthead Mobile',        format: 'Image',  size: '360×200',   reach: 28, vi: 78, ctr: 0.48, cpm: 35000, objectives: ['awareness'],                 siteUrl: LEGACY_SITE_URLS.ZingNews,  adspilotUrl: legacyZoneUrl('ZN.Masthead.Mobile') },
  { id: 'ZN.Sidebar.Desktop',   platform: 'ZingNews',   placement: 'Sidebar',  name: 'Sidebar Desktop',        format: 'Image',  size: '300×600',   reach: 12, vi: 71, ctr: 0.32, cpm: 25000, objectives: ['awareness','consideration'], siteUrl: LEGACY_SITE_URLS.ZingNews,  adspilotUrl: legacyZoneUrl('ZN.Sidebar.Desktop') },
  { id: 'ZN.Feed.Native',       platform: 'ZingNews',   placement: 'Feed',     name: 'Feed Native',            format: 'Native', size: '1200×628',  reach: 22, vi: 72, ctr: 1.10, cpm: 32000, objectives: ['consideration'],             siteUrl: LEGACY_SITE_URLS.ZingNews,  adspilotUrl: legacyZoneUrl('ZN.Feed.Native') },
  // ── BaoMoi ──────────────────────────────────────────────────────────────────
  { id: 'BM.Background.Desktop',platform: 'BaoMoi',     placement: 'Background',name:'Background Roadblock',   format: 'Image',  size: '1800×1000', reach: 15, vi: 88, ctr: 0.42, cpm: 55000, objectives: ['awareness'],                 siteUrl: LEGACY_SITE_URLS.BaoMoi, adspilotUrl: legacyZoneUrl('BM.Background.Desktop') },
  { id: 'BM.Feed.Native',       platform: 'BaoMoi',     placement: 'Feed',     name: 'Feed Native',            format: 'Native', size: '1200×628',  reach: 19, vi: 69, ctr: 0.98, cpm: 28000, objectives: ['consideration','conversion'], siteUrl: LEGACY_SITE_URLS.BaoMoi, adspilotUrl: legacyZoneUrl('BM.Feed.Native') },
  { id: 'BM.Masthead.Mobile',   platform: 'BaoMoi',     placement: 'Masthead', name: 'Masthead Mobile',        format: 'Image',  size: '360×200',   reach: 24, vi: 76, ctr: 0.52, cpm: 38000, objectives: ['awareness'],                 siteUrl: LEGACY_SITE_URLS.BaoMoi, adspilotUrl: legacyZoneUrl('BM.Masthead.Mobile') },
  // ── ZingMP3 ─────────────────────────────────────────────────────────────────
  { id: 'ZMP3.Masthead.Mobile', platform: 'ZingMP3',    placement: 'Masthead', name: 'Masthead Mobile',        format: 'Image',  size: '360×200',   reach: 16, vi: 80, ctr: 0.44, cpm: 40000, objectives: ['awareness'],                 siteUrl: LEGACY_SITE_URLS.ZingMP3, adspilotUrl: legacyZoneUrl('ZMP3.Masthead.Mobile') },
  { id: 'ZMP3.Player.Banner',   platform: 'ZingMP3',    placement: 'Player',   name: 'Player Banner',          format: 'Banner', size: '1080×180',  reach: 20, vi: 83, ctr: 0.38, cpm: 32000, objectives: ['awareness','consideration'], siteUrl: LEGACY_SITE_URLS.ZingMP3, adspilotUrl: legacyZoneUrl('ZMP3.Player.Banner') },
  { id: 'ZMP3.Video.PreRoll',   platform: 'ZingMP3',    placement: 'Video',    name: 'Pre-Roll Video',         format: 'Video',  size: '1080×1920', reach: 12, vi: 91, ctr: 0.85, cpm: 52000, objectives: ['awareness','consideration'], siteUrl: LEGACY_SITE_URLS.ZingMP3, adspilotUrl: legacyZoneUrl('ZMP3.Video.PreRoll') },
]

// ─── Reason templates ────────────────────────────────────────────────────────
// This small catalog is a legacy fallback used by the manual setup and result
// screens. Keep its ranking data stable, but resolve every navigable URL from
// the deployment environment so an isolated stack cannot escape to production.
export const ALL_ZONES = RAW_ZONES.map(zone => ({
  ...zone,
  siteUrl: zone.siteUrl ? (LEGACY_SITE_URLS[zone.platform] || zone.siteUrl) : null,
  adspilotUrl: `${LEGACY_BACKEND_URL}/api/zones?id=${encodeURIComponent(zone.id)}`,
}))

const REASONS = {
  'MSG.Story.Fullscreen': 'Format fullscreen, VI 93% — tối ưu brand recall cho awareness.',
  'MSG.Story.Video':      'Video immersive, VI 95% — storytelling hiệu quả, gây ấn tượng mạnh.',
  'MSG.InApp.Reward':     'VI 97% + CTR 1.4% cao nhất — người dùng chủ động xem, phù hợp conversion.',
  'MSG.Feed.Native1':     'CTR 1.45% + reach 41M — hiệu quả cao, ngân sách tối ưu nhất.',
  'MSG.Inbox.Banner':     'Reach 38M + CPM 17k rẻ nhất — phủ rộng, tiết kiệm budget.',
  'MSG.Feed.Native2':     'CTR 1.3% + reach 36M — bổ sung reach song song với Native 1.',
  'ZN.Masthead.Desktop':  'Vị trí đầu trang tin tức, cao điểm sáng — premium placement.',
  'ZN.Masthead.Mobile':   'Reach 28M mobile — phủ mobile ZingNews hiệu quả.',
  'BM.Background.Desktop':'Roadblock 100% share of voice — impact mạnh trên BaoMoi.',
  'ZMP3.Video.PreRoll':   'VI 91%, audience nhạc số — context phù hợp lifestyle.',
}

// ─── Score zone for an objective ──────────────────────────────────────────────
function scoreZone(zone, objective) {
  switch (objective) {
    case 'awareness':
      return zone.reach * 0.4 + zone.vi * 0.35 + (100000 / zone.cpm) * 0.25
    case 'conversion':
      return zone.ctr * 0.5 + (100000 / zone.cpm) * 0.3 + zone.vi * 0.2
    case 'consideration':
      return zone.ctr * 0.35 + zone.reach * 0.3 + zone.vi * 0.35
    case 'retention':
      return zone.vi * 0.5 + zone.ctr * 0.3 + (100000 / zone.cpm) * 0.2
    default:
      return zone.reach * 0.4 + zone.vi * 0.4 + zone.ctr * 0.2
  }
}

// ─── Get recommended zones (top 5 for objective) ─────────────────────────────
export function getRecommendedZones(objective = 'awareness', budget = 100) {
  const scored = ALL_ZONES
    .map(z => ({ ...z, score: scoreZone(z, objective) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 6)
    .map(z => ({
      ...z,
      reason: REASONS[z.id] || `Phù hợp mục tiêu ${objective}, hiệu suất tốt trong nhóm ngành.`,
    }))
  return scored
}

// ─── Calc estimated impressions for a zone given budget (triệu VND) ──────────
export function calcImpressions(zone, budgetM) {
  // budgetM in triệu VND, cpm in VND/1000 impressions
  return Math.round((budgetM * 1_000_000) / zone.cpm * 1000)
}

// ─── Format large number ─────────────────────────────────────────────────────
export function fmtReach(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K'
  return String(n)
}
