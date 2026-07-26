const DCC_API_BASE = ['localhost', '127.0.0.1'].includes(location.hostname)
  ? 'http://localhost:3000/api'
  : 'https://api.pawgrammers.io.vn/api';
const DCC_ALLOW_FALLBACK = window.__ADSTACK_CONFIG__?.allowFallbackAds ?? true;

function dccEscape(value) {
  return String(value || '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function dccTrack(path, payload) {
  fetch(`${DCC_API_BASE}/ads/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, siteId: 'dicungcon.vn' }),
    keepalive: true,
  }).catch(() => {});
}

function dccFallback(zoneId) {
  const rail = zoneId.includes('SidebarRail');
  return `<a class="fallback-ad ${rail ? 'rail-creative' : 'bridge-creative'}" href="#parenting" aria-label="Quảng cáo mô phỏng">
    <span class="ad-label">${rail ? 'Vị trí thử nghiệm · reserved_layout' : 'Quảng cáo mô phỏng'}</span>
    ${rail ? '<span class="fallback-copy"><b>Cùng con khám phá</b><span>Học hỏi · Vui chơi · Kết nối</span></span>' : ''}
  </a>`;
}

function dccLiveCreative(ad, zoneId) {
  const image = ad.creative?.imageUrl || ad.creative?.url;
  if (!image || !/^(https?:|\/)/.test(image)) return dccFallback(zoneId);
  const target = /^(https?:|\/|#)/.test(ad.clickUrl || '') ? ad.clickUrl : '#';
  return `<a class="live-ad" href="${dccEscape(target)}" target="_blank" rel="noopener">
    <span class="ad-label">Quảng cáo</span><img src="${dccEscape(image)}" alt="${dccEscape(ad.brand || 'Quảng cáo')}">
  </a>`;
}

async function dccMount(zoneId) {
  const element = document.getElementById(zoneId);
  if (!element) return;
  let ad = null;
  try {
    const response = await fetch(
      `${DCC_API_BASE}/ads/check?zone=${encodeURIComponent(zoneId)}&site=${encodeURIComponent('dicungcon.vn')}`,
      { signal: AbortSignal.timeout(4000) },
    );
    if (response.ok) ad = (await response.json()).ad;
  } catch (_error) {
    ad = null;
  }
  if (!ad) {
    if (DCC_ALLOW_FALLBACK) element.innerHTML = dccFallback(zoneId);
    return;
  }
  element.innerHTML = dccLiveCreative(ad, zoneId);
  dccTrack('impression', { campaignId: ad.campaignId, placementId: ad.placementId || zoneId });
  element.querySelector('a')?.addEventListener('click', () => {
    dccTrack('click', { campaignId: ad.campaignId, placementId: ad.placementId || zoneId });
  }, { once: true });
}

document.addEventListener('DOMContentLoaded', () => {
  const mobile = matchMedia('(max-width: 760px)').matches;
  const zones = mobile
    ? ['DiCungCon_ContentBridge_Mobile']
    : ['DiCungCon_ContentBridge_Desktop', 'DiCungCon_SidebarRail_Desktop'];
  zones.forEach(dccMount);
});
