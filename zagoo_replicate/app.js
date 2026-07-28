const ZAGOO_API_BASE = ['localhost', '127.0.0.1'].includes(location.hostname)
  ? 'http://localhost:3000/api'
  : 'https://api.pawgrammers.io.vn/api';
const ZAGOO_ALLOW_FALLBACK = window.__ADSTACK_CONFIG__?.allowFallbackAds ?? true;

function zagooEscape(value) {
  return String(value || '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function zagooTrack(path, payload) {
  fetch(`${ZAGOO_API_BASE}/ads/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, siteId: 'zagoo.vn' }),
    keepalive: true,
  }).catch(() => {});
}

function zagooFallback(zoneId) {
  const mobile = zoneId.includes('Mobile');
  return `<a class="fallback-ad ${mobile ? 'mobile-creative' : 'desktop-creative'}" href="#discover" aria-label="Quảng cáo trò chơi mô phỏng">
    <span class="ad-label">Quảng cáo mô phỏng</span>
  </a>`;
}

function zagooLiveCreative(ad, zoneId) {
  const image = ad.creative?.imageUrl || ad.creative?.url;
  if (!image || !/^(https?:|\/)/.test(image)) return zagooFallback(zoneId);
  const target = /^(https?:|\/|#)/.test(ad.clickUrl || '') ? ad.clickUrl : '#';
  return `<a class="live-ad" href="${zagooEscape(target)}" target="_blank" rel="noopener">
    <span class="ad-label">Quảng cáo</span><img src="${zagooEscape(image)}" alt="${zagooEscape(ad.brand || 'Quảng cáo')}">
  </a>`;
}

async function zagooMount(zoneId) {
  const element = document.getElementById(zoneId);
  if (!element) return;
  let ad = null;
  try {
    const response = await fetch(
      `${ZAGOO_API_BASE}/ads/check?zone=${encodeURIComponent(zoneId)}&site=${encodeURIComponent('zagoo.vn')}`,
      { signal: AbortSignal.timeout(4000) },
    );
    if (response.ok) ad = (await response.json()).ad;
  } catch (_error) {
    ad = null;
  }
  if (!ad) {
    if (ZAGOO_ALLOW_FALLBACK) element.innerHTML = zagooFallback(zoneId);
    return;
  }
  element.innerHTML = zagooLiveCreative(ad, zoneId);
  zagooTrack('impression', { campaignId: ad.campaignId, placementId: ad.placementId || zoneId });
  element.querySelector('a')?.addEventListener('click', () => {
    zagooTrack('click', { campaignId: ad.campaignId, placementId: ad.placementId || zoneId });
  }, { once: true });
}

document.addEventListener('DOMContentLoaded', () => {
  const mobile = matchMedia('(max-width: 760px)').matches;
  zagooMount(mobile ? 'Zagoo_Interstitial_Mobile' : 'Zagoo_Interstitial_Desktop');
  document.getElementById('close-interstitial')?.addEventListener('click', () => {
    document.getElementById('zagoo-overlay')?.classList.add('closed');
  });
});
