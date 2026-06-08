/**
 * AdsPilot / Ad Server Integration Boilerplate
 * This client fetches active campaign ads for specific zones.
 */

// Configuration for the Ad Server API
const AD_SERVER_CONFIG = {
    // In production, point this to your actual Ad Server URL (e.g., VNG Cloud Runtime or Local mock)
    baseURL: 'http://localhost:8080/api',
    timeout: 3000,
    siteInfo: 'znews.vn'
};

// Create an Axios instance if Axios is available
let adApiClient = null;
if (typeof axios !== 'undefined') {
    adApiClient = axios.create({
        baseURL: AD_SERVER_CONFIG.baseURL,
        timeout: AD_SERVER_CONFIG.timeout
    });
}

/**
 * Fetch ad content for a specific placement zone.
 * If the API call fails or the server is offline, it falls back to a curated mock ad.
 * 
 * @param {string} zoneId - ID of the ad placement zone (e.g. ZingNews_Masthead, ZingNews_Halfpage)
 * @returns {Promise<Object>} Ad response object containing html, targetUrl, and ad status
 */
async function fetchAdForZone(zoneId) {
    console.log(`[AdAgent] Requesting ad for zone: ${zoneId}...`);
    
    const params = {
        zoneId: zoneId,
        site: AD_SERVER_CONFIG.siteInfo,
        t: Date.now() // Prevent caching
    };

    try {
        if (!adApiClient) {
            throw new Error('Axios is not loaded yet.');
        }
        
        // Boilerplate GET request to check for campaign placement
        const response = await adApiClient.get('/ads/check', { params });
        if (response.data && response.data.hasAd) {
            return response.data;
        } else {
            return getFallbackMockAd(zoneId);
        }
    } catch (error) {
        console.warn(`[AdAgent] Ad Server API request failed for zone ${zoneId}. Using offline mock database.`, error.message);
        // Fallback to high-quality mockup data matching campaign briefs
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve(getFallbackMockAd(zoneId));
            }, 300 + Math.random() * 500); // Simulate network latency
        });
    }
}

/**
 * Curated offline fallback database mapping the ad zones to the 
 * hackathon briefs (Mazda CX-5, FlyDragon Airlines, NeoCard Finance).
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
                    <div style="max-width: 1160px; width: 100%; aspect-ratio: 1160 / 250; margin: 0 auto;">
                        <a href="https://mazda.com.vn" target="_blank" style="display: block; width: 100%; height: 100%;">
                            <img src="ad-pic/top-banner.jpg" style="width: 100%; height: 100%; object-fit: contain; border: none; display: block;" alt="Mazda Ad">
                        </a>
                    </div>
                `
            };

        case 'ZingNews_Halfpage': // Top Right Sidebar (300x600)
            return {
                hasAd: true,
                campaignId: 'ORD-2026-002',
                brand: 'FlyDragon Airlines',
                targetUrl: 'https://flydragon.com.vn',
                html: `
                    <a href="https://flydragon.com.vn" target="_blank" style="display: block; width: 100%; height: 100%;">
                        <img src="ad-pic/side-banner.jpg" style="width: 100%; height: 100%; object-fit: cover; border: none; display: block;" alt="Sidebar Ad 1">
                    </a>
                `
            };

        case 'ZingNews_PrBox_2': // Bottom Right Sidebar (300x250)
            return {
                hasAd: true,
                campaignId: 'ORD-2026-003',
                brand: 'NeoCard Finance',
                targetUrl: 'https://neocard.com.vn',
                html: `
                    <a href="https://neocard.com.vn" target="_blank" style="display: block; width: 100%; height: 100%;">
                        <img src="ad-pic/side-banner.jpg" style="width: 100%; height: 100%; object-fit: cover; border: none; display: block;" alt="Sidebar Ad 2">
                    </a>
                `
            };

        case 'ZingNews_Masthead_Inline_1': // Middle Inline (970x250)
            return {
                hasAd: true,
                campaignId: 'ORD-2026-004',
                brand: 'VinFast VF 3',
                targetUrl: 'https://vinfastauto.com',
                html: `
                    <a href="https://vinfastauto.com" target="_blank" style="display: block; width: 100%; height: 100%;">
                        <img src="ad-pic/middle-banner.jpg" style="width: 100%; height: 100%; object-fit: cover; border: none; display: block;" alt="Middle Ad">
                    </a>
                `
            };

        default:
            if (zoneId.includes('Background')) {
                return {
                    hasAd: true,
                    targetUrl: 'https://example.com/skin',
                    html: `
                        <a href="https://example.com/skin" target="_blank" style="display: block; width: 100%; height: 100%; min-height: 1080px; text-indent: -9999px;">Skin Ad</a>
                        <style>
                            body {
                                background-image: url('ad-pic/Background.png');
                                background-attachment: fixed;
                                background-position: center top;
                                background-repeat: no-repeat;
                                background-color: #f1f1f1;
                            }
                            /* Offset the main content so we can see the top of the skin ad */
                            /* Remove margin-top so the wrapper naturally sits below the header */
                            .page-wrapper.category-page {
                                background-color: transparent;
                                padding-top: 20px;
                            }
                        </style>
                    `
                };
            } else if (zoneId.includes('SideLeft')) {
                return {
                    hasAd: true,
                    targetUrl: 'https://example.com/side-left',
                    html: `
                        <a href="https://example.com/side-left" target="_blank" style="display: block; width: 100%; height: 100%;">
                            <img src="ad-pic/Left.png" style="width: 100%; height: 100%; object-fit: cover; border: none; display: block;" alt="Side Left Ad">
                        </a>
                    `
                };
            } else if (zoneId.includes('SideRight')) {
                return {
                    hasAd: true,
                    targetUrl: 'https://example.com/side-right',
                    html: `
                        <a href="https://example.com/side-right" target="_blank" style="display: block; width: 100%; height: 100%;">
                            <img src="ad-pic/Right.png" style="width: 100%; height: 100%; object-fit: cover; border: none; display: block;" alt="Side Right Ad">
                        </a>
                    `
                };
            } else if (zoneId.includes('SidebarBox')) {
                return {
                    hasAd: true,
                    targetUrl: 'https://example.com/sidebar',
                    html: `
                        <a href="https://example.com/sidebar" target="_blank" style="display: block; width: 100%; height: 100%;">
                            <img src="ad-pic/side-banner.jpg" style="width: 100%; height: 100%; object-fit: cover; border: none; display: block;" alt="Sidebar Ad">
                        </a>
                    `
                };
            }
            return { hasAd: false };
    }
}
