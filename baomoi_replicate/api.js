/**
 * AdsPilot / Ad Server Integration — BaoMoi Replicate
 * Fetches live campaign ads from the real backend and tracks impressions/clicks.
 *
 * Response shape from backend GET /api/ads/check:
 *   { ad: { campaignId, placementId, brand, creative: { url, format }, clickUrl }, zone, site }
 *   or { ad: null, zone, site }
 *
 * Normalises backend response into { hasAd, html, imageUrl, ... } shape that app.js expects.
 */

// ── Config ──────────────────────────────────────────────────────────────────
const _isVPS  = !window.location.hostname.includes('localhost') && !window.location.hostname.includes('127.0.0.1');
const AD_API_BASE = _isVPS
    ? 'https://api.pawgrammers.io.vn/api'
    : 'http://localhost:3000/api';

const AD_SITE_ID  = 'baomoi.com';
const AD_TIMEOUT  = 4000;

// ── Impression / Click Tracking ──────────────────────────────────────────────
function trackImpression(campaignId, placementId) {
    if (!campaignId || !placementId) return;
    fetch(`${AD_API_BASE}/ads/impression`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ campaignId, placementId, siteId: AD_SITE_ID }),
        keepalive: true
    }).catch(() => {});
}

function trackClick(campaignId, placementId) {
    if (!campaignId || !placementId) return;
    fetch(`${AD_API_BASE}/ads/click`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ campaignId, placementId, siteId: AD_SITE_ID }),
        keepalive: true
    }).catch(() => {});
}

// ── Core Fetch with Timeout ──────────────────────────────────────────────────
function fetchWithTimeout(url, options = {}, timeout = AD_TIMEOUT) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    return fetch(url, { ...options, signal: controller.signal })
        .finally(() => clearTimeout(id));
}

// ── Helper: Check Image Exists ───────────────────────────────────────────────
async function checkImageExists(url) {
    try {
        const r = await fetch(url, { method: 'HEAD' });
        return r.ok;
    } catch (e) {
        return false;
    }
}

// ── Creative HTML Builder ────────────────────────────────────────────────────
/**
 * Builds BaoMoi-style ad HTML from a backend creative object.
 * Mirrors the structure in getFallbackMockAd but uses live data.
 */
async function buildCreativeHtml(ad, zoneId) {
    const campaignId  = ad.campaignId;
    const placementId = ad.placementId || zoneId;
    const targetUrl   = ad.clickUrl || ad.creative?.url || '#';
    const brand       = ad.brand || 'Ad';
    const onClickAttr = `onclick="trackClick('${campaignId}','${placementId}'); return true;"`;

    // Determine image URL: remote creative or local fallback
    const remoteImg = ad.creative?.imageUrl || ad.creative?.url || null;
    const fallbackImg = getFallbackImageForZone(zoneId);
    const imageUrl  = (remoteImg && remoteImg.startsWith('http')) ? remoteImg : fallbackImg;
    const hasImage  = imageUrl ? await checkImageExists(imageUrl) : false;

    switch (zoneId) {
        case 'BaoMoi_Background':
            return {
                html: hasImage
                    ? `<a href="${targetUrl}" target="_blank" ${onClickAttr} style="display:block;width:100%;height:100%;"></a>`
                    : `<a href="${targetUrl}" target="_blank" ${onClickAttr} style="display:block;width:100%;height:100%;"></a>`,
                imageUrl
            };

        case 'BaoMoi_Masthead':
            return {
                html: hasImage
                    ? `<div class="ad-wrapper" style="height:280px;">
                         <span class="ad-close-btn">&times;</span>
                         <a href="${targetUrl}" target="_blank" ${onClickAttr}>
                             <img src="${imageUrl}" alt="${brand}">
                         </a>
                         <span class="ad-label-tag">Quảng cáo</span>
                       </div>`
                    : `<div class="ad-wrapper" style="height:280px;">
                         <span class="ad-close-btn">&times;</span>
                         <a href="${targetUrl}" target="_blank" ${onClickAttr} class="ad-fallback-gradient" style="background:linear-gradient(135deg,#1f1c2c 0%,#928dab 100%);">
                             <div class="brand">${brand}</div>
                             <div class="tagline">Quảng cáo được phân phối bởi AdsPilot</div>
                             <div class="cta">Tìm hiểu ngay</div>
                             <span class="ad-label-tag">Quảng cáo</span>
                         </a>
                       </div>`
            };

        case 'BaoMoi_StickyLeft':
            return {
                html: hasImage
                    ? `<div class="ad-wrapper">
                         <span class="ad-close-btn">&times;</span>
                         <a href="${targetUrl}" target="_blank" ${onClickAttr}>
                             <img src="${imageUrl}" alt="${brand}">
                         </a>
                       </div>`
                    : `<div class="ad-wrapper">
                         <span class="ad-close-btn">&times;</span>
                         <a href="${targetUrl}" target="_blank" ${onClickAttr} class="ad-fallback-gradient" style="background:linear-gradient(180deg,#ef32d9 0%,#89fffd 100%);">
                             <div class="brand">${brand}</div>
                             <div class="tagline">Powered by AdsPilot</div>
                             <div class="cta">Tìm hiểu</div>
                             <span class="ad-label-tag">QC</span>
                         </a>
                       </div>`
            };

        case 'BaoMoi_StickyRight':
            return {
                html: hasImage
                    ? `<div class="ad-wrapper">
                         <span class="ad-close-btn">&times;</span>
                         <a href="${targetUrl}" target="_blank" ${onClickAttr}>
                             <img src="${imageUrl}" alt="${brand}">
                         </a>
                       </div>`
                    : `<div class="ad-wrapper">
                         <span class="ad-close-btn">&times;</span>
                         <a href="${targetUrl}" target="_blank" ${onClickAttr} class="ad-fallback-gradient" style="background:linear-gradient(180deg,#89fffd 0%,#ef32d9 100%);">
                             <div class="brand">${brand}</div>
                             <div class="tagline">Powered by AdsPilot</div>
                             <div class="cta">Tìm hiểu</div>
                             <span class="ad-label-tag">QC</span>
                         </a>
                       </div>`
            };

        case 'BaoMoi_Box1':
            return {
                html: hasImage
                    ? `<div class="ad-wrapper" style="min-height:250px;">
                         <span class="ad-close-btn">&times;</span>
                         <a href="${targetUrl}" target="_blank" ${onClickAttr}>
                             <img src="${imageUrl}" alt="${brand}">
                         </a>
                         <span class="ad-label-tag">Quảng cáo</span>
                       </div>`
                    : `<div class="ad-wrapper" style="min-height:250px;aspect-ratio:300/250;">
                         <span class="ad-close-btn">&times;</span>
                         <a href="${targetUrl}" target="_blank" ${onClickAttr} class="ad-fallback-gradient" style="background:linear-gradient(135deg,#0f2027 0%,#203a43 50%,#2c5364 100%);">
                             <div class="brand">${brand}</div>
                             <div class="tagline">Powered by AdsPilot</div>
                             <div class="cta">Xem ngay</div>
                             <span class="ad-label-tag">Quảng cáo</span>
                         </a>
                       </div>`
            };

        case 'BaoMoi_Box2':
            return {
                html: hasImage
                    ? `<div class="ad-wrapper" style="min-height:600px;">
                         <span class="ad-close-btn">&times;</span>
                         <a href="${targetUrl}" target="_blank" ${onClickAttr}>
                             <img src="${imageUrl}" alt="${brand}">
                         </a>
                         <span class="ad-label-tag">Quảng cáo</span>
                       </div>`
                    : `<div class="ad-wrapper" style="min-height:600px;aspect-ratio:300/600;">
                         <span class="ad-close-btn">&times;</span>
                         <a href="${targetUrl}" target="_blank" ${onClickAttr} class="ad-fallback-gradient" style="background:linear-gradient(135deg,#3a7bd5 0%,#3a6073 100%);">
                             <div class="brand">${brand}</div>
                             <div class="tagline">Powered by AdsPilot</div>
                             <div class="cta">Xem ngay</div>
                             <span class="ad-label-tag">Quảng cáo</span>
                         </a>
                       </div>`
            };

        default:
            return { html: '' };
    }
}

function getFallbackImageForZone(zoneId) {
    if (zoneId === 'BaoMoi_Background')   return 'ad-pic/background-ad.jpg';
    if (zoneId === 'BaoMoi_StickyLeft')   return 'ad-pic/Left.png';
    if (zoneId === 'BaoMoi_StickyRight')  return 'ad-pic/Right.png';
    if (zoneId === 'BaoMoi_Box1')         return 'ad-pic/sidebar-ad1.jpg';
    if (zoneId === 'BaoMoi_Box2')         return 'ad-pic/sidebar-ad2.jpg';
    return 'ad-pic/top-banner.jpg';
}

// ── Public API ───────────────────────────────────────────────────────────────
/**
 * Fetch ad content for a specific placement zone.
 * Hits the real backend first; falls back to curated mock on error.
 *
 * @param {string} zoneId
 * @returns {Promise<{hasAd, html, imageUrl?, brand?, targetUrl?}>}
 */
async function fetchAdForZone(zoneId) {
    console.log(`[AdAgent] Requesting ad for zone: ${zoneId} from ${AD_API_BASE}`);

    try {
        const url = `${AD_API_BASE}/ads/check?zone=${encodeURIComponent(zoneId)}&site=${encodeURIComponent(AD_SITE_ID)}`;
        const response = await fetchWithTimeout(url, {}, AD_TIMEOUT);

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        if (data && data.ad) {
            const ad = data.ad;
            const creative = await buildCreativeHtml(ad, zoneId);

            // Fire impression immediately
            trackImpression(ad.campaignId, ad.placementId || zoneId);

            console.log(`[AdAgent] Live ad loaded for ${zoneId} → campaign ${ad.campaignId}`);
            return {
                hasAd:      true,
                campaignId: ad.campaignId,
                placementId: ad.placementId || zoneId,
                brand:      ad.brand,
                targetUrl:  ad.clickUrl || '',
                imageUrl:   creative.imageUrl || null,
                html:       creative.html
            };
        }

        console.log(`[AdAgent] No live campaign for ${zoneId}. Using fallback.`);
        return getFallbackMockAd(zoneId);

    } catch (error) {
        console.warn(`[AdAgent] Backend unreachable for zone ${zoneId}: ${error.message}. Using fallback.`);
        return new Promise(resolve =>
            setTimeout(() => resolve(getFallbackMockAd(zoneId)), 200 + Math.random() * 300)
        );
    }
}

// ── Fallback Mock Database ───────────────────────────────────────────────────
async function getFallbackMockAd(zoneId) {
    let ad = { hasAd: true };

    switch (zoneId) {
        case 'BaoMoi_Background':
            ad.brand = 'Mastercard';
            ad.targetUrl = 'https://mastercard.com.vn';
            ad.imageUrl = 'ad-pic/background-ad.jpg';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = `<a href="${ad.targetUrl}" target="_blank" style="display:block;width:100%;height:100%;"></a>`;
            break;

        case 'BaoMoi_Masthead':
            ad.brand = 'Mazda CX-5';
            ad.targetUrl = 'https://mazda.com.vn';
            ad.imageUrl = 'ad-pic/top-banner.jpg';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = ad.hasImage
                ? `<div class="ad-wrapper" style="height:280px;">
                     <span class="ad-close-btn">&times;</span>
                     <a href="${ad.targetUrl}" target="_blank"><img src="${ad.imageUrl}" alt="${ad.brand}"></a>
                     <span class="ad-label-tag">Quảng cáo</span>
                   </div>`
                : `<div class="ad-wrapper" style="height:280px;">
                     <span class="ad-close-btn">&times;</span>
                     <a href="${ad.targetUrl}" target="_blank" class="ad-fallback-gradient" style="background:linear-gradient(135deg,#1f1c2c 0%,#928dab 100%);">
                         <div class="brand">${ad.brand}</div>
                         <div class="tagline">Kiệt Tác Thiết Kế - Đỉnh Cao Công Nghệ</div>
                         <div class="cta">Tìm hiểu ngay</div>
                         <span class="ad-label-tag">Quảng cáo</span>
                     </a>
                   </div>`;
            break;

        case 'BaoMoi_StickyLeft':
            ad.brand = 'FlyDragon Left';
            ad.targetUrl = 'https://flydragon.com.vn';
            ad.imageUrl = 'ad-pic/Left.png';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = ad.hasImage
                ? `<div class="ad-wrapper"><span class="ad-close-btn">&times;</span><a href="${ad.targetUrl}" target="_blank"><img src="${ad.imageUrl}" alt="${ad.brand}"></a></div>`
                : `<div class="ad-wrapper"><span class="ad-close-btn">&times;</span><a href="${ad.targetUrl}" target="_blank" class="ad-fallback-gradient" style="background:linear-gradient(180deg,#ef32d9 0%,#89fffd 100%);"><div class="brand">FlyDragon</div><div class="tagline">Trải Nghiệm Bay Thượng Lưu</div><div class="cta">Đặt vé ngay</div><span class="ad-label-tag">QC</span></a></div>`;
            break;

        case 'BaoMoi_StickyRight':
            ad.brand = 'FlyDragon Right';
            ad.targetUrl = 'https://flydragon.com.vn';
            ad.imageUrl = 'ad-pic/Right.png';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = ad.hasImage
                ? `<div class="ad-wrapper"><span class="ad-close-btn">&times;</span><a href="${ad.targetUrl}" target="_blank"><img src="${ad.imageUrl}" alt="${ad.brand}"></a></div>`
                : `<div class="ad-wrapper"><span class="ad-close-btn">&times;</span><a href="${ad.targetUrl}" target="_blank" class="ad-fallback-gradient" style="background:linear-gradient(180deg,#89fffd 0%,#ef32d9 100%);"><div class="brand">FlyDragon</div><div class="tagline">Trải Nghiệm Bay Thượng Lưu</div><div class="cta">Đặt vé ngay</div><span class="ad-label-tag">QC</span></a></div>`;
            break;

        case 'BaoMoi_Box1':
            ad.brand = 'NeoCard';
            ad.targetUrl = 'https://neocard.com.vn';
            ad.imageUrl = 'ad-pic/sidebar-ad1.jpg';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = ad.hasImage
                ? `<div class="ad-wrapper" style="min-height:250px;"><span class="ad-close-btn">&times;</span><a href="${ad.targetUrl}" target="_blank"><img src="${ad.imageUrl}" alt="${ad.brand}"></a><span class="ad-label-tag">Quảng cáo</span></div>`
                : `<div class="ad-wrapper" style="min-height:250px;aspect-ratio:300/250;"><span class="ad-close-btn">&times;</span><a href="${ad.targetUrl}" target="_blank" class="ad-fallback-gradient" style="background:linear-gradient(135deg,#0f2027 0%,#203a43 50%,#2c5364 100%);"><div class="brand">NeoCard</div><div class="tagline">Thế Hệ Thẻ Tín Dụng Mới</div><div class="cta">Đăng ký online</div><span class="ad-label-tag">Quảng cáo</span></a></div>`;
            break;

        case 'BaoMoi_Box2':
            ad.brand = 'VinFast VF 3';
            ad.targetUrl = 'https://vinfastauto.com';
            ad.imageUrl = 'ad-pic/sidebar-ad2.jpg';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = ad.hasImage
                ? `<div class="ad-wrapper" style="min-height:600px;"><span class="ad-close-btn">&times;</span><a href="${ad.targetUrl}" target="_blank"><img src="${ad.imageUrl}" alt="${ad.brand}"></a><span class="ad-label-tag">Quảng cáo</span></div>`
                : `<div class="ad-wrapper" style="min-height:600px;aspect-ratio:300/600;"><span class="ad-close-btn">&times;</span><a href="${ad.targetUrl}" target="_blank" class="ad-fallback-gradient" style="background:linear-gradient(135deg,#3a7bd5 0%,#3a6073 100%);"><div class="brand">VinFast VF 3</div><div class="tagline">Xe Điện Quốc Dân Đột Phá</div><div class="cta">Đặt cọc ngay</div><span class="ad-label-tag">Quảng cáo</span></a></div>`;
            break;

        default:
            ad.hasAd = false;
    }

    return ad;
}
