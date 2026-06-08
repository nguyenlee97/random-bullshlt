/**
 * ZingMP3 Ads API Integration Client
 * Handles requests to the Ad Server and returns templates.
 */

const AD_SERVER_CONFIG = {
    // In production, point this to your actual Ad Server URL
    apiEndpoint: 'http://localhost:3000/api/ads/check',
    timeout: 3000,
    retryCount: 2
};

const AdsPilotClient = {
    /**
     * Checks if there's an active campaign ad for a given zone.
     * @param {string} zoneId - The target ad zone ID (e.g. 'ZingMP3_Masthead')
     * @returns {Promise<object>} Ad campaign object
     */
    async checkAd(zoneId) {
        console.log(`[AdsPilot] Checking ads for zone: ${zoneId}...`);
        
        try {
            // Attempt to query the ad server
            const response = await axios.post(AD_SERVER_CONFIG.apiEndpoint, {
                zoneId: zoneId,
                site: 'zingmp3',
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                }
            }, {
                timeout: AD_SERVER_CONFIG.timeout
            });

            if (response.data && response.data.hasAd) {
                console.log(`[AdsPilot] Campaign ad found for ${zoneId}:`, response.data);
                return response.data;
            } else {
                console.log(`[AdsPilot] No active campaign on server for ${zoneId}. Using offline fallback.`);
                return getFallbackMockAd(zoneId);
            }
        } catch (error) {
            console.warn(`[AdsPilot] Ad server connection failed (${error.message}). Using offline fallback.`);
            return getFallbackMockAd(zoneId);
        }
    }
};

/**
 * Curated offline fallback database mapping the ad zones.
 * If the user places their ad image at 'ad-pic/top-banner.jpg', it will load.
 * Otherwise, it shows a premium gradient placeholder.
 */
function getFallbackMockAd(zoneId) {
    switch (zoneId) {
        case 'ZingMP3_Masthead':
            return {
                hasAd: true,
                campaignId: 'ZMP3-CAMP-2026',
                brand: 'ZingMP3 Campaign',
                targetUrl: 'https://zingmp3.vn',
                html: `
                    <a href="https://zingmp3.vn" target="_blank" style="display: block; width: 100%; height: 100%; text-decoration: none;">
                        <img src="ad-pic/top-banner.jpg" 
                             onerror="this.style.display='none'; document.getElementById('zmp3-placeholder-gradient').style.display='flex';" 
                             style="width: 100%; height: 100%; object-fit: contain; border: none; display: block;" 
                             alt="ZingMP3 Campaign Ad">
                        <div id="zmp3-placeholder-gradient" style="display: none; width: 100%; height: 100%; justify-content: center; align-items: center; flex-direction: column; background: linear-gradient(135deg, #7200a1 0%, #340d4e 100%); color: #ffffff; font-family: 'Inter', sans-serif; gap: 8px;">
                            <div style="font-size: 20px; font-weight: 700; letter-spacing: 0.5px; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">
                                ZingMP3 Campaign Ad Zone
                            </div>
                            <div style="font-size: 13px; color: rgba(255,255,255,0.6); font-weight: 400;">
                                Place your 'top-banner.jpg' inside the 'ad-pic/' directory to load
                            </div>
                        </div>
                    </a>
                `
            };
        default:
            return { hasAd: false };
    }
}
