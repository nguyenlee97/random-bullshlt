const ZNEWS_PATHS = {
  'znews-site': '/',
  'znews-kinh-doanh': '/kinh-doanh.html',
  'znews-suc-khoe': '/suc-khoe.html',
  'znews-the-thao': '/the-thao.html',
  'znews-doi-song': '/doi-song.html',
  'znews-cong-nghe': '/cong-nghe.html',
  'znews-giai-tri': '/giai-tri.html',
};

function joinUrl(base, path = '/') {
  return `${String(base || '').replace(/\/$/, '')}${path}`;
}

function publicSiteUrl(placement, env = process.env) {
  if (env.SITE_URL_MODE !== 'local') return placement.siteUrl || null;

  if (placement.siteId === 'znews' || String(placement.channel || '').startsWith('znews-')) {
    return joinUrl(env.LOCAL_ZNEWS_URL || 'http://localhost:5176', ZNEWS_PATHS[placement.channel] || '/');
  }
  if (placement.siteId === 'baomoi' || placement.channel === 'baomoi-site') {
    return joinUrl(env.LOCAL_BAOMOI_URL || 'http://localhost:5177');
  }
  if (placement.siteId === 'zingmp3' || placement.channel === 'zingmp3-site') {
    return joinUrl(env.LOCAL_ZINGMP3_URL || 'http://localhost:5178');
  }
  return placement.siteUrl || null;
}

function withPublicSiteUrl(placement, env = process.env) {
  const plain = placement && typeof placement.toObject === 'function'
    ? placement.toObject()
    : { ...placement };
  return { ...plain, siteUrl: publicSiteUrl(plain, env) };
}

module.exports = { publicSiteUrl, withPublicSiteUrl };
