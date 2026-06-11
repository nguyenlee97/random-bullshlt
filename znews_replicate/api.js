/**
 * AdsPilot / Ad Server Integration — Znews Replicate
 * Fetches live campaign ads from the real backend and tracks impressions/clicks.
 *
 * Response shape from backend GET /api/ads/check:
 *   { ad: { campaignId, placementId, brand, creative: { url, format }, clickUrl }, zone, site }
 *   or { ad: null, zone, site }
 *
 * This file normalises the backend response into the { hasAd, html, campaignId, ... }
 * shape that app.js expects, then fires impression/click events.
 */

// ── Config ──────────────────────────────────────────────────────────────────
// AD_API_BASE is detected at runtime:
//   • On VPS (production) → relative path hits the same origin's Nginx proxy
//   • Locally → absolute localhost:3000
const _isVPS  = !window.location.hostname.includes('localhost') && !window.location.hostname.includes('127.0.0.1');
const AD_API_BASE = _isVPS
    ? 'https://api.pawgrammers.io.vn/api'
    : 'http://localhost:3000/api';

const AD_SITE_ID  = 'znews.vn';
const AD_TIMEOUT  = 4000; // ms before giving up on backend

// ── Impression / Click Tracking ──────────────────────────────────────────────
/**
 * Fire-and-forget POST to record an impression.
 */
function trackImpression(campaignId, placementId) {
    if (!campaignId || !placementId) return;
    fetch(`${AD_API_BASE}/ads/impression`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ campaignId, placementId, siteId: AD_SITE_ID }),
        keepalive: true
    }).catch(() => {}); // Silently ignore network errors
}

/**
 * Fire-and-forget POST to record a click.
 */
function trackClick(campaignId, placementId) {
    if (!campaignId || !placementId) return;
    fetch(`${AD_API_BASE}/ads/click`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ campaignId, placementId, siteId: AD_SITE_ID }),
        keepalive: true
    }).catch(() => {});
}

// ── Creative HTML Builder ────────────────────────────────────────────────────
/**
 * Builds the ad HTML from the backend creative object.
 * Falls back to the local fallback image if no remote creative is available.
 */
function buildCreativeHtml(ad, zoneId) {
    const campaignId  = ad.campaignId;
    const placementId = ad.placementId || zoneId;
    const targetUrl   = ad.clickUrl || ad.creative?.url || '#';
    const imageUrl    = ad.creative?.imageUrl || ad.creative?.url || null;
    const brand       = ad.brand || 'Ad';

    // Tracking wrapper: intercept clicks on the link
    const onClickAttr = `onclick="trackClick('${campaignId}','${placementId}'); return true;"`;

    // Decide image src (remote creative → fallback local asset)
    let imgSrc = null;
    if (imageUrl && (imageUrl.startsWith('http') || imageUrl.startsWith('/'))) {
        imgSrc = imageUrl;
    } else {
        imgSrc = getFallbackImageForZone(zoneId);
    }

    // Background/skin zone – special CSS injection
    if (zoneId.includes('Background')) {
        const bgSrc = imgSrc || 'ad-pic/Background.png';
        return `
            <a href="${targetUrl}" target="_blank" ${onClickAttr}
               style="display:block;width:100%;height:100%;min-height:1080px;text-indent:-9999px;">Skin Ad</a>
            <style>
                body {
                    background-image: url('${bgSrc}');
                    background-attachment: fixed;
                    background-position: center top;
                    background-repeat: no-repeat;
                    background-color: #f1f1f1;
                }
                .page-wrapper.category-page {
                    background-color: transparent;
                    padding-top: 20px;
                }
            </style>
        `;
    }

    if (zoneId.includes('SideLeft')) {
        return `
            <a href="${targetUrl}" target="_blank" ${onClickAttr}
               style="display:block;width:100%;height:100%;">
                <img src="${imgSrc || 'ad-pic/Left.png'}"
                     style="width:100%;height:100%;object-fit:cover;border:none;display:block;" alt="${brand}">
            </a>`;
    }

    if (zoneId.includes('SideRight')) {
        return `
            <a href="${targetUrl}" target="_blank" ${onClickAttr}
               style="display:block;width:100%;height:100%;">
                <img src="${imgSrc || 'ad-pic/Right.png'}"
                     style="width:100%;height:100%;object-fit:cover;border:none;display:block;" alt="${brand}">
            </a>`;
    }

    if (zoneId.includes('SidebarBox') || zoneId.includes('PrBox') || zoneId.includes('Halfpage')) {
        return `
            <a href="${targetUrl}" target="_blank" ${onClickAttr}
               style="display:block;width:100%;height:100%;">
                <img src="${imgSrc || 'ad-pic/side-banner.jpg'}"
                     style="width:100%;height:100%;object-fit:cover;border:none;display:block;" alt="${brand}">
            </a>`;
    }

    // Masthead / inline banner (default)
    return `
        <div style="max-width:1160px;width:100%;aspect-ratio:1160/250;margin:0 auto;">
            <a href="${targetUrl}" target="_blank" ${onClickAttr}
               style="display:block;width:100%;height:100%;">
                <img src="${imgSrc || 'ad-pic/top-banner.jpg'}"
                     style="width:100%;height:100%;object-fit:contain;border:none;display:block;" alt="${brand}">
            </a>
        </div>`;
}

function getFallbackImageForZone(zoneId) {
    if (zoneId.includes('SideLeft'))  return 'ad-pic/Left.png';
    if (zoneId.includes('SideRight')) return 'ad-pic/Right.png';
    if (zoneId.includes('Background')) return 'ad-pic/Background.png';
    if (zoneId.includes('Halfpage') || zoneId.includes('PrBox') || zoneId.includes('Sidebar')) return 'ad-pic/side-banner.jpg';
    if (zoneId.includes('Inline'))    return 'ad-pic/middle-banner.jpg';
    return 'ad-pic/top-banner.jpg';
}

// ── Core Fetch with Timeout ──────────────────────────────────────────────────
function fetchWithTimeout(url, options = {}, timeout = AD_TIMEOUT) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    return fetch(url, { ...options, signal: controller.signal })
        .finally(() => clearTimeout(id));
}

// ── Public API ───────────────────────────────────────────────────────────────
/**
 * Fetch ad content for a specific placement zone.
 * Hits the real backend first; falls back to curated mock on error.
 *
 * @param {string} zoneId - Ad placement zone ID (e.g. 'ZingNews_Masthead')
 * @returns {Promise<{hasAd, html, campaignId, brand, targetUrl}>}
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
            const html = buildCreativeHtml(ad, zoneId);

            // Fire impression immediately after successful ad load
            trackImpression(ad.campaignId, ad.placementId || zoneId);

            console.log(`[AdAgent] Live ad loaded for ${zoneId} → campaign ${ad.campaignId}`);
            return {
                hasAd:      true,
                campaignId: ad.campaignId,
                placementId: ad.placementId || zoneId,
                brand:      ad.brand,
                targetUrl:  ad.clickUrl || '',
                html
            };
        }

        // Backend responded but no active campaign → use fallback
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
/**
 * Curated offline fallback. Mirrors real campaign brands for demo continuity.
 * Used when backend is unreachable or returns no active campaign.
 */
function getFallbackMockAd(zoneId) {
    switch (zoneId) {
        case 'ZingNews_Masthead':
            return {
                hasAd: true,
                campaignId: 'ORD-2026-001',
                brand: 'Mazda CX-5',
                targetUrl: 'https://mazda.com.vn',
                html: `
                    <div style="max-width:1160px;width:100%;aspect-ratio:1160/250;margin:0 auto;">
                        <a href="https://mazda.com.vn" target="_blank" style="display:block;width:100%;height:100%;">
                            <img src="ad-pic/top-banner.jpg" style="width:100%;height:100%;object-fit:contain;border:none;display:block;" alt="Mazda Ad">
                        </a>
                    </div>`
            };

        case 'ZingNews_Halfpage':
            return {
                hasAd: true,
                campaignId: 'ORD-2026-002',
                brand: 'FlyDragon Airlines',
                targetUrl: 'https://flydragon.com.vn',
                html: `
                    <a href="https://flydragon.com.vn" target="_blank" style="display:block;width:100%;height:100%;">
                        <img src="ad-pic/side-banner.jpg" style="width:100%;height:100%;object-fit:cover;border:none;display:block;" alt="Sidebar Ad">
                    </a>`
            };

        case 'ZingNews_PrBox_2':
            return {
                hasAd: true,
                campaignId: 'ORD-2026-003',
                brand: 'NeoCard Finance',
                targetUrl: 'https://neocard.com.vn',
                html: `
                    <a href="https://neocard.com.vn" target="_blank" style="display:block;width:100%;height:100%;">
                        <img src="ad-pic/side-banner.jpg" style="width:100%;height:100%;object-fit:cover;border:none;display:block;" alt="Sidebar Ad 2">
                    </a>`
            };

        case 'ZingNews_Masthead_Inline_1':
            return {
                hasAd: true,
                campaignId: 'ORD-2026-004',
                brand: 'VinFast VF 3',
                targetUrl: 'https://vinfastauto.com',
                html: `
                    <a href="https://vinfastauto.com" target="_blank" style="display:block;width:100%;height:100%;">
                        <img src="ad-pic/middle-banner.jpg" style="width:100%;height:100%;object-fit:cover;border:none;display:block;" alt="Middle Ad">
                    </a>`
            };

        default:
            if (zoneId.includes('Background')) {
                return {
                    hasAd: true,
                    targetUrl: 'https://example.com/skin',
                    html: `
                        <a href="https://example.com/skin" target="_blank" style="display:block;width:100%;height:100%;min-height:1080px;text-indent:-9999px;">Skin Ad</a>
                        <style>
                            body { background-image: url('ad-pic/Background.png'); background-attachment: fixed; background-position: center top; background-repeat: no-repeat; background-color: #f1f1f1; }
                            .page-wrapper.category-page { background-color: transparent; padding-top: 20px; }
                        </style>`
                };
            } else if (zoneId.includes('SideLeft')) {
                return { hasAd: true, targetUrl: 'https://example.com/side-left',
                    html: `<a href="https://example.com/side-left" target="_blank" style="display:block;width:100%;height:100%;"><img src="ad-pic/Left.png" style="width:100%;height:100%;object-fit:cover;border:none;display:block;" alt="Side Left Ad"></a>` };
            } else if (zoneId.includes('SideRight')) {
                return { hasAd: true, targetUrl: 'https://example.com/side-right',
                    html: `<a href="https://example.com/side-right" target="_blank" style="display:block;width:100%;height:100%;"><img src="ad-pic/Right.png" style="width:100%;height:100%;object-fit:cover;border:none;display:block;" alt="Side Right Ad"></a>` };
            } else if (zoneId.includes('SidebarBox')) {
                return { hasAd: true, targetUrl: 'https://example.com/sidebar',
                    html: `<a href="https://example.com/sidebar" target="_blank" style="display:block;width:100%;height:100%;"><img src="ad-pic/side-banner.jpg" style="width:100%;height:100%;object-fit:cover;border:none;display:block;" alt="Sidebar Ad"></a>` };
            }
            return { hasAd: false };
    }
}
