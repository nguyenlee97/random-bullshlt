/**
 * BaoMoi Replicate - Ad Client API Integration
 */

const AD_SERVER_CONFIG = {
    baseURL: 'http://localhost:8080/api',
    timeout: 3000,
    siteInfo: 'baomoi.com'
};

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
 */
async function fetchAdForZone(zoneId) {
    console.log(`[AdAgent] Requesting ad for zone: ${zoneId}...`);
    
    const params = {
        zoneId: zoneId,
        site: AD_SERVER_CONFIG.siteInfo,
        t: Date.now()
    };

    try {
        if (!adApiClient) {
            throw new Error('Axios is not loaded yet.');
        }
        const response = await adApiClient.get('/ads/check', { params });
        if (response.data && response.data.hasAd) {
            return response.data;
        } else {
            return getFallbackMockAd(zoneId);
        }
    } catch (error) {
        console.warn(`[AdAgent] Ad Server API request failed for zone ${zoneId}. Using offline mock database.`);
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve(getFallbackMockAd(zoneId));
            }, 200 + Math.random() * 300);
        });
    }
}

/**
 * Helper to check if a local image file exists.
 * Because we are client-side, we can test it using a quick fetch/HEAD request.
 */
async function checkImageExists(url) {
    try {
        const response = await fetch(url, { method: 'HEAD' });
        return response.ok;
    } catch (e) {
        return false;
    }
}

/**
 * Curated offline fallback database mapping the ad zones to the hackathon briefs.
 */
async function getFallbackMockAd(zoneId) {
    let ad = { hasAd: true };

    switch (zoneId) {
        case 'BaoMoi_Background':
            ad.brand = 'Mastercard';
            ad.targetUrl = 'https://mastercard.com.vn';
            ad.imageUrl = 'ad-pic/background-ad.jpg';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = ad.hasImage 
                ? `<a href="${ad.targetUrl}" target="_blank" style="display:block; width:100%; height:100%;"></a>`
                : `<a href="${ad.targetUrl}" target="_blank" style="display:block; width:100%; height:100%;"></a>`;
            break;

        case 'BaoMoi_Masthead':
            ad.brand = 'Mazda CX-5';
            ad.targetUrl = 'https://mazda.com.vn';
            ad.imageUrl = 'ad-pic/top-banner.jpg';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = ad.hasImage 
                ? `
                    <div class="ad-wrapper" style="height: 280px;">
                        <span class="ad-close-btn">&times;</span>
                        <a href="${ad.targetUrl}" target="_blank">
                            <img src="${ad.imageUrl}" alt="${ad.brand}">
                        </a>
                        <span class="ad-label-tag">Quảng cáo</span>
                    </div>
                `
                : `
                    <div class="ad-wrapper" style="height: 280px;">
                        <span class="ad-close-btn">&times;</span>
                        <a href="${ad.targetUrl}" target="_blank" class="ad-fallback-gradient" style="background: linear-gradient(135deg, #1f1c2c 0%, #928dab 100%);">
                            <div class="brand">${ad.brand}</div>
                            <div class="tagline">Kiệt Tác Thiết Kế - Đỉnh Cao Công Nghệ</div>
                            <div class="cta">Tìm hiểu ngay</div>
                            <span class="ad-label-tag">Quảng cáo</span>
                        </a>
                    </div>
                `;
            break;

        case 'BaoMoi_StickyLeft':
            ad.brand = 'FlyDragon Left';
            ad.targetUrl = 'https://flydragon.com.vn';
            ad.imageUrl = 'ad-pic/Left.png';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = ad.hasImage 
                ? `
                    <div class="ad-wrapper">
                        <span class="ad-close-btn">&times;</span>
                        <a href="${ad.targetUrl}" target="_blank">
                            <img src="${ad.imageUrl}" alt="${ad.brand}">
                        </a>
                    </div>
                `
                : `
                    <div class="ad-wrapper">
                        <span class="ad-close-btn">&times;</span>
                        <a href="${ad.targetUrl}" target="_blank" class="ad-fallback-gradient" style="background: linear-gradient(180deg, #ef32d9 0%, #89fffd 100%);">
                            <div class="brand">FlyDragon</div>
                            <div class="tagline">Trải Nghiệm Bay Thượng Lưu</div>
                            <div class="cta">Đặt vé ngay</div>
                            <span class="ad-label-tag">QC</span>
                        </a>
                    </div>
                `;
            break;

        case 'BaoMoi_StickyRight':
            ad.brand = 'FlyDragon Right';
            ad.targetUrl = 'https://flydragon.com.vn';
            ad.imageUrl = 'ad-pic/Right.png';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = ad.hasImage 
                ? `
                    <div class="ad-wrapper">
                        <span class="ad-close-btn">&times;</span>
                        <a href="${ad.targetUrl}" target="_blank">
                            <img src="${ad.imageUrl}" alt="${ad.brand}">
                        </a>
                    </div>
                `
                : `
                    <div class="ad-wrapper">
                        <span class="ad-close-btn">&times;</span>
                        <a href="${ad.targetUrl}" target="_blank" class="ad-fallback-gradient" style="background: linear-gradient(180deg, #89fffd 0%, #ef32d9 100%);">
                            <div class="brand">FlyDragon</div>
                            <div class="tagline">Trải Nghiệm Bay Thượng Lưu</div>
                            <div class="cta">Đặt vé ngay</div>
                            <span class="ad-label-tag">QC</span>
                        </a>
                    </div>
                `;
            break;

        case 'BaoMoi_Box1':
            ad.brand = 'NeoCard';
            ad.targetUrl = 'https://neocard.com.vn';
            ad.imageUrl = 'ad-pic/sidebar-ad1.jpg';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = ad.hasImage 
                ? `
                    <div class="ad-wrapper" style="min-height: 250px;">
                        <span class="ad-close-btn">&times;</span>
                        <a href="${ad.targetUrl}" target="_blank">
                            <img src="${ad.imageUrl}" alt="${ad.brand}">
                        </a>
                        <span class="ad-label-tag">Quảng cáo</span>
                    </div>
                `
                : `
                    <div class="ad-wrapper" style="min-height: 250px; aspect-ratio: 300 / 250;">
                        <span class="ad-close-btn">&times;</span>
                        <a href="${ad.targetUrl}" target="_blank" class="ad-fallback-gradient" style="background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);">
                            <div class="brand">NeoCard</div>
                            <div class="tagline">Thế Hệ Thẻ Tín Dụng Mới</div>
                            <div class="cta">Đăng ký online</div>
                            <span class="ad-label-tag">Quảng cáo</span>
                        </a>
                    </div>
                `;
            break;

        case 'BaoMoi_Box2':
            ad.brand = 'VinFast VF 3';
            ad.targetUrl = 'https://vinfastauto.com';
            ad.imageUrl = 'ad-pic/sidebar-ad2.jpg';
            ad.hasImage = await checkImageExists(ad.imageUrl);
            ad.html = ad.hasImage 
                ? `
                    <div class="ad-wrapper" style="min-height: 600px;">
                        <span class="ad-close-btn">&times;</span>
                        <a href="${ad.targetUrl}" target="_blank">
                            <img src="${ad.imageUrl}" alt="${ad.brand}">
                        </a>
                        <span class="ad-label-tag">Quảng cáo</span>
                    </div>
                `
                : `
                    <div class="ad-wrapper" style="min-height: 600px; aspect-ratio: 300 / 600;">
                        <span class="ad-close-btn">&times;</span>
                        <a href="${ad.targetUrl}" target="_blank" class="ad-fallback-gradient" style="background: linear-gradient(135deg, #3a7bd5 0%, #3a6073 100%);">
                            <div class="brand">VinFast VF 3</div>
                            <div class="tagline">Xe Điện Quốc Dân Đột Phá</div>
                            <div class="cta">Đặt cọc ngay</div>
                            <span class="ad-label-tag">Quảng cáo</span>
                        </a>
                    </div>
                `;
            break;

        default:
            ad.hasAd = false;
    }

    return ad;
}
