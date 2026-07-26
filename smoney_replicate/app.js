const SMONEY_API_BASE = ['localhost', '127.0.0.1'].includes(location.hostname)
  ? 'http://localhost:3000/api'
  : 'https://api.pawgrammers.io.vn/api';
const SMONEY_ALLOW_FALLBACK = window.__ADSTACK_CONFIG__?.allowFallbackAds ?? true;

function smoneyEscape(value) {
  return String(value || '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function smoneyTrack(path, payload) {
  fetch(`${SMONEY_API_BASE}/ads/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, siteId: 'smoney.vn' }),
    keepalive: true,
  }).catch(() => {});
}

function smoneyFallback(zoneId) {
  const screener = zoneId.includes('StockScreener');
  return `<a class="fallback-ad ${screener ? 'screener-creative' : 'top-creative'}" href="#screener" aria-label="Quảng cáo mô phỏng">
    <span class="ad-label">Quảng cáo mô phỏng</span>
    <span class="fallback-ad-copy"><b>${screener ? 'Quảng cáo bộ lọc cổ phiếu' : 'S.Vision'}</b></span>
  </a>`;
}

function smoneyLiveCreative(ad, zoneId) {
  const image = ad.creative?.imageUrl || ad.creative?.url;
  if (!image || !/^(https?:|\/)/.test(image)) return smoneyFallback(zoneId);
  const target = /^(https?:|\/|#)/.test(ad.clickUrl || '') ? ad.clickUrl : '#';
  return `<a class="live-ad" href="${smoneyEscape(target)}" target="_blank" rel="noopener">
    <span class="ad-label">Quảng cáo</span><img src="${smoneyEscape(image)}" alt="${smoneyEscape(ad.brand || 'Quảng cáo')}">
  </a>`;
}

async function smoneyMount(zoneId) {
  const element = document.getElementById(zoneId);
  if (!element) return;
  let ad = null;
  try {
    const response = await fetch(
      `${SMONEY_API_BASE}/ads/check?zone=${encodeURIComponent(zoneId)}&site=${encodeURIComponent('smoney.vn')}`,
      { signal: AbortSignal.timeout(4000) },
    );
    if (response.ok) ad = (await response.json()).ad;
  } catch (_error) {
    ad = null;
  }
  if (!ad) {
    if (SMONEY_ALLOW_FALLBACK) element.innerHTML = smoneyFallback(zoneId);
    return;
  }
  element.innerHTML = smoneyLiveCreative(ad, zoneId);
  smoneyTrack('impression', { campaignId: ad.campaignId, placementId: ad.placementId || zoneId });
  element.querySelector('a')?.addEventListener('click', () => {
    smoneyTrack('click', { campaignId: ad.campaignId, placementId: ad.placementId || zoneId });
  }, { once: true });
}

document.addEventListener('DOMContentLoaded', () => {
  const mobile = matchMedia('(max-width: 760px)').matches;
  const zones = mobile
    ? ['SMoney_TopPromo_Mobile', 'SMoney_StockScreener_InContent_Mobile']
    : ['SMoney_TopPromo_Desktop', 'SMoney_StockScreener_InContent_Desktop'];
  zones.forEach(smoneyMount);
});
