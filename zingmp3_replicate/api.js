/**
 * AdsPilot / Ad Server Integration — ZingMP3 Replicate
 * Fetches live campaign ads from the real backend and tracks impressions/clicks.
 *
 * Response shape from backend GET /api/ads/check:
 *   { ad: { campaignId, placementId, brand, creative: { url, format }, clickUrl }, zone, site }
 *   or { ad: null, zone, site }
 *
 * Exposes `AdsPilotClient.checkAd(zoneId)` returning { hasAd, html, campaignId, ... }
 * — same interface as before so app.js needs no changes.
 */

// ── Config ──────────────────────────────────────────────────────────────────
const _isVPS  = !window.location.hostname.includes('localhost') && !window.location.hostname.includes('127.0.0.1');
const AD_API_BASE = _isVPS
    ? 'https://api.pawgrammers.io.vn/api'
    : 'http://localhost:3000/api';

const AD_SITE_ID  = 'zingmp3.vn';
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

// ── Creative HTML Builder ────────────────────────────────────────────────────
function buildCreativeHtml(ad, zoneId) {
    const campaignId  = ad.campaignId;
    const placementId = ad.placementId || zoneId;
    const targetUrl   = ad.clickUrl || ad.creative?.url || '#';
    const brand       = ad.brand || 'ZingMP3 Campaign';
    const onClickAttr = `onclick="trackClick('${campaignId}','${placementId}'); return true;"`;

    const remoteImg = ad.creative?.imageUrl || ad.creative?.url || null;
    const imgSrc = (remoteImg && remoteImg.startsWith('http')) ? remoteImg : 'ad-pic/top-banner.jpg';

    // ZingMP3 only has the Masthead zone — build its template
    return `
        <a href="${targetUrl}" target="_blank" ${onClickAttr}
           style="display:block;width:100%;height:100%;text-decoration:none;">
            <img src="${imgSrc}"
                 onerror="this.style.display='none'; document.getElementById('zmp3-placeholder-gradient').style.display='flex';"
                 style="width:100%;height:100%;object-fit:contain;border:none;display:block;"
                 alt="${brand}">
            <div id="zmp3-placeholder-gradient"
                 style="display:none;width:100%;height:100%;justify-content:center;align-items:center;flex-direction:column;background:linear-gradient(135deg,#7200a1 0%,#340d4e 100%);color:#ffffff;font-family:'Inter',sans-serif;gap:8px;">
                <div style="font-size:20px;font-weight:700;letter-spacing:0.5px;text-shadow:0 2px 4px rgba(0,0,0,0.3);">
                    ${brand}
                </div>
                <div style="font-size:13px;color:rgba(255,255,255,0.6);font-weight:400;">
                    Powered by AdsPilot
                </div>
            </div>
        </a>`;
}

// ── Public API ───────────────────────────────────────────────────────────────
const AdsPilotClient = {
    /**
     * Checks if there's an active campaign ad for a given zone.
     * @param {string} zoneId - e.g. 'ZingMP3_Masthead'
     * @returns {Promise<{hasAd, html, campaignId?, brand?, targetUrl?}>}
     */
    async checkAd(zoneId) {
        console.log(`[AdsPilot] Checking ads for zone: ${zoneId} from ${AD_API_BASE}`);

        try {
            const url = `${AD_API_BASE}/ads/check?zone=${encodeURIComponent(zoneId)}&site=${encodeURIComponent(AD_SITE_ID)}`;
            const response = await fetchWithTimeout(url, {}, AD_TIMEOUT);

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();

            if (data && data.ad) {
                const ad = data.ad;
                const html = buildCreativeHtml(ad, zoneId);

                // Fire impression immediately
                trackImpression(ad.campaignId, ad.placementId || zoneId);

                console.log(`[AdsPilot] Live ad loaded for ${zoneId} → campaign ${ad.campaignId}`);
                return {
                    hasAd:       true,
                    campaignId:  ad.campaignId,
                    placementId: ad.placementId || zoneId,
                    brand:       ad.brand,
                    targetUrl:   ad.clickUrl || '',
                    html
                };
            }

            console.log(`[AdsPilot] No live campaign for ${zoneId}. Using fallback.`);
            return getFallbackMockAd(zoneId);

        } catch (error) {
            console.warn(`[AdsPilot] Ad server connection failed (${error.message}). Using offline fallback.`);
            return getFallbackMockAd(zoneId);
        }
    }
};

// ── Fallback Mock Database ───────────────────────────────────────────────────
function getFallbackMockAd(zoneId) {
    switch (zoneId) {
        case 'ZingMP3_Masthead':
            return {
                hasAd: true,
                campaignId: 'ZMP3-CAMP-2026',
                brand: 'ZingMP3 Campaign',
                targetUrl: 'https://zingmp3.vn',
                html: `
                    <a href="https://zingmp3.vn" target="_blank"
                       style="display:block;width:100%;height:100%;text-decoration:none;">
                        <img src="ad-pic/top-banner.jpg"
                             onerror="this.style.display='none'; document.getElementById('zmp3-placeholder-gradient').style.display='flex';"
                             style="width:100%;height:100%;object-fit:contain;border:none;display:block;"
                             alt="ZingMP3 Campaign Ad">
                        <div id="zmp3-placeholder-gradient"
                             style="display:none;width:100%;height:100%;justify-content:center;align-items:center;flex-direction:column;background:linear-gradient(135deg,#7200a1 0%,#340d4e 100%);color:#ffffff;font-family:'Inter',sans-serif;gap:8px;">
                            <div style="font-size:20px;font-weight:700;letter-spacing:0.5px;text-shadow:0 2px 4px rgba(0,0,0,0.3);">
                                ZingMP3 Campaign Ad Zone
                            </div>
                            <div style="font-size:13px;color:rgba(255,255,255,0.6);font-weight:400;">
                                Place your 'top-banner.jpg' inside the 'ad-pic/' directory to load
                            </div>
                        </div>
                    </a>`
            };
        default:
            return { hasAd: false };
    }
}
