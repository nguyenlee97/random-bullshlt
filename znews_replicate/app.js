/**
 * Znews Replicate - Ads & Media Integration Manager
 */

// Target Zones in Znews page
const AD_ZONES = {
    masthead: 'ZingNews_Masthead',
    halfpage: 'ZingNews_Halfpage',
    prbox2: 'ZingNews_PrBox_2',
    inline: 'ZingNews_Masthead_Inline_1'
};

document.addEventListener("DOMContentLoaded", () => {
    console.log("[AdAgent] Page loaded. Initializing ad slots and media lazy-loading...");
    
    // Load top banner and sidebar ads immediately
    initAdSlot(AD_ZONES.masthead);
    initAdSlot(AD_ZONES.halfpage);
    initAdSlot(AD_ZONES.prbox2);
    
    // Initialize dynamic ad containers by data-zone
    document.querySelectorAll('.ad-container[data-zone]').forEach(container => {
        initAdSlot(container.getAttribute('data-zone'), container);
    });

    // Sticky Side Ads Logic (Simulate sticky while keeping absolute positioning)
    window.addEventListener('scroll', () => {
        const sideAds = document.querySelectorAll('.sticky-ad');
        const scrollY = window.scrollY;
        // page-wrapper has margin-top: 250px.
        // The side ads have initial top: 300px.
        // At scrollY = 450px, the ad hits 100px from the top of the viewport.
        const triggerScrollY = 450;
        const initialTop = 300;
        sideAds.forEach(ad => {
            if (scrollY > triggerScrollY) {
                ad.style.top = (initialTop + (scrollY - triggerScrollY)) + 'px';
            } else {
                ad.style.top = initialTop + 'px';
            }
        });
    });
    
    // Setup lazy loading scroll observer for the inline middle ad
    setupScrollAdObserver();

    // Setup media lazy loading for all images containing data-src attributes
    setupImageLazyLoader();

    // Populate static market widgets under Kinh doanh
    populateMarketWidgets();

    // Populate static match schedule widget
    populateScheduleWidget();
});

/**
 * Clean up the pre-existing ad element and trigger loading
 */
function initAdSlot(zoneId, element = null) {
    const el = element || document.getElementById(zoneId);
    if (!el) {
        console.warn(`[AdAgent] Ad element #${zoneId} not found in the DOM.`);
        return;
    }

    // Add our custom styling while preserving existing classes
    el.classList.add("znews-banner");
    el.innerHTML = `
        <div class="ad-loader">
            <div class="spinner"></div>
            <span>Đang tải quảng cáo...</span>
        </div>
    `;

    // Fetch ad content from api.js
    fetchAdForZone(zoneId).then(adData => {
        if (adData && adData.hasAd && adData.html) {
            el.innerHTML = adData.html;
            el.classList.add("loaded");
            console.log(`[AdAgent] Ad successfully loaded inside #${zoneId}`);
        } else {
            const size = el.getAttribute("size") || "Responsive";
            el.innerHTML = `
                <div class="ad-empty-placeholder">
                    <span class="placeholder-tag">QC</span>
                    <span class="placeholder-size">${size}</span>
                </div>
            `;
        }
    });
}

/**
 * Intersection Observer for scroll-triggered inline ad zone
 */
function setupScrollAdObserver() {
    const inlineEl = document.getElementById(AD_ZONES.inline);
    if (!inlineEl) return;

    // Set initial custom banner class
    inlineEl.className = "znews-banner";
    
    let hasLoaded = false;
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !hasLoaded) {
                hasLoaded = true;
                console.log(`[AdAgent] Zone #${AD_ZONES.inline} scrolled into view. Triggering fetch...`);
                initAdSlot(AD_ZONES.inline);
                observer.unobserve(entry.target);
            }
        });
    }, {
        rootMargin: "150px 0px" // Load ad slightly before scroll boundary
    });

    observer.observe(inlineEl);
}

/**
 * Custom lazy-loader for image elements utilizing data-src attributes
 */
function setupImageLazyLoader() {
    const lazyImages = document.querySelectorAll('img[data-src]');
    console.log(`[AdAgent] Found ${lazyImages.length} lazy-loadable images.`);
    
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        // Trigger layout recalculation if needed
                        img.removeAttribute('data-src');
                    }
                    imageObserver.unobserve(img);
                }
            });
        }, {
            rootMargin: "300px 0px" // Load images 300px before they reach viewport
        });
        
        lazyImages.forEach(img => imageObserver.observe(img));
    } else {
        // Fallback for older browsers
        lazyImages.forEach(img => {
            if (img.dataset.src) {
                img.src = img.dataset.src;
            }
        });
    }
}

/**
 * Populate SJC Gold, Foreign Exchange, and Stock indices widgets statically
 */
function populateMarketWidgets() {
    console.log("[AdAgent] Populating market widget data...");
    
    // Remove the 'loading' class from the wrapper if it exists
    const widgetSection = document.querySelector('.widget-business');
    if (widgetSection) {
        widgetSection.classList.remove('loading');
    }

    // 1. Gold SJC
    const goldWidget = document.getElementById('widget-gold');
    if (goldWidget) {
        const values = goldWidget.querySelectorAll('.value');
        if (values.length >= 2) {
            values[0].textContent = '149.200.000';
            values[1].textContent = '153.200.000';
        }
    }

    // 2. Exchange Rates
    const exchangeWidget = document.getElementById('widget-exchange');
    if (exchangeWidget) {
        const details = exchangeWidget.querySelectorAll('.detail');
        details.forEach(detail => {
            const brandEl = detail.querySelector('.brand');
            if (!brandEl) return;
            const brand = brandEl.textContent.trim().toUpperCase();
            const values = detail.querySelectorAll('.value');
            if (values.length >= 2) {
                if (brand === 'USD') {
                    values[0].textContent = '26.150';
                    values[1].textContent = '26.404';
                } else if (brand === 'EUR') {
                    values[0].textContent = '30.275';
                    values[1].textContent = '31.184';
                }
            }
        });
    }

    // 3. Stock Market
    const stockWidget = document.getElementById('widget-stock');
    if (stockWidget) {
        const details = stockWidget.querySelectorAll('.detail');
        details.forEach(detail => {
            const brandEl = detail.querySelector('.brand');
            if (!brandEl) return;
            const brand = brandEl.textContent.trim().toUpperCase();
            const priceEl = detail.querySelector('.price');
            const percentEl = detail.querySelector('.percent');
            if (brand === 'VNINDEX') {
                if (priceEl) priceEl.innerHTML = '1.838,9 <i class="ic-up" style="color: #078243; font-style: normal; font-weight: bold; margin-left: 2px;">▲</i>';
                if (percentEl) {
                    percentEl.textContent = '0,4%';
                    percentEl.style.color = '#078243';
                    percentEl.style.fontWeight = 'bold';
                }
            } else if (brand === 'HNX') {
                if (priceEl) priceEl.innerHTML = '293,79 <i class="ic-down" style="color: #e30a17; font-style: normal; font-weight: bold; margin-left: 2px;">▼</i>';
                if (percentEl) {
                    percentEl.textContent = '-3,63%';
                    percentEl.style.color = '#e30a17';
                    percentEl.style.fontWeight = 'bold';
                }
            } else if (brand === 'UPCOM') {
                if (priceEl) priceEl.innerHTML = '125,09 <i class="ic-down" style="color: #e30a17; font-style: normal; font-weight: bold; margin-left: 2px;">▼</i>';
                if (percentEl) {
                    percentEl.textContent = '-0,61%';
                    percentEl.style.color = '#e30a17';
                    percentEl.style.fontWeight = 'bold';
                }
            }
        });
    }
}

/**
 * Populate the schedule list widget with matches HTML statically
 */
function populateScheduleWidget() {
    console.log("[AdAgent] Populating schedule widget data...");
    const scheduleContainer = document.querySelector('.schedule-list');
    if (!scheduleContainer) {
        console.warn("[AdAgent] .schedule-list container not found.");
        return;
    }

    scheduleContainer.innerHTML = `
        <a class="wc2026-schedule-home-item__inner" href="https://znews.vn/worldcup-2026/mexico-vs-nam-phi-tran-dau-513493.html" style="display: block; text-decoration: none; color: inherit;">
            <span style="display: flex; gap: 8px; font-size: 11px; color: #888; margin-bottom: 4px;">
                <span>Bảng A</span>
                <span>•</span>
                <span>Thứ 6, 12/06/2026</span>
            </span>
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 8px; width: 40%;">
                    <img src="https://flagcdn.com/w40/mx.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                    <span style="font-weight: 500; font-size: 13px;">Mexico</span>
                </div>
                <div style="width: 20%; text-align: center; font-weight: bold; font-size: 13px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">
                    <span>02:00</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px; justify-content: flex-end; width: 40%;">
                    <span style="font-weight: 500; font-size: 13px;">Nam Phi</span>
                    <img src="https://flagcdn.com/w40/za.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                </div>
            </div>
        </a>
        <a class="wc2026-schedule-home-item__inner" href="https://znews.vn/worldcup-2026/han-quoc-vs-cong-hoa-sec-tran-dau-513494.html" style="display: block; text-decoration: none; color: inherit; margin-top: 12px; border-top: 1px solid #f1f5f9; padding-top: 12px;">
            <span style="display: flex; gap: 8px; font-size: 11px; color: #888; margin-bottom: 4px;">
                <span>Bảng F</span>
                <span>•</span>
                <span>Thứ 6, 12/06/2026</span>
            </span>
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 8px; width: 40%;">
                    <img src="https://flagcdn.com/w40/kr.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                    <span style="font-weight: 500; font-size: 13px;">Hàn Quốc</span>
                </div>
                <div style="width: 20%; text-align: center; font-weight: bold; font-size: 13px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">
                    <span>09:00</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px; justify-content: flex-end; width: 40%;">
                    <span style="font-weight: 500; font-size: 13px;">Cộng hòa Séc</span>
                    <img src="https://flagcdn.com/w40/cz.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                </div>
            </div>
        </a>
        <a class="wc2026-schedule-home-item__inner" href="https://znews.vn/worldcup-2026/canada-vs-bosnia-and-herzegovina-tran-dau-513495.html" style="display: block; text-decoration: none; color: inherit; margin-top: 12px; border-top: 1px solid #f1f5f9; padding-top: 12px;">
            <span style="display: flex; gap: 8px; font-size: 11px; color: #888; margin-bottom: 4px;">
                <span>Bảng B</span>
                <span>•</span>
                <span>Thứ 7, 13/06/2026</span>
            </span>
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 8px; width: 40%;">
                    <img src="https://flagcdn.com/w40/ca.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                    <span style="font-weight: 500; font-size: 13px;">Canada</span>
                </div>
                <div style="width: 20%; text-align: center; font-weight: bold; font-size: 13px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">
                    <span>02:00</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px; justify-content: flex-end; width: 40%;">
                    <span style="font-weight: 500; font-size: 13px;">Bosnia...</span>
                    <img src="https://flagcdn.com/w40/ba.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                </div>
            </div>
        </a>
        <a class="wc2026-schedule-home-item__inner" href="https://znews.vn/worldcup-2026/my-vs-paraguay-tran-dau-513505.html" style="display: block; text-decoration: none; color: inherit; margin-top: 12px; border-top: 1px solid #f1f5f9; padding-top: 12px;">
            <span style="display: flex; gap: 8px; font-size: 11px; color: #888; margin-bottom: 4px;">
                <span>Bảng D</span>
                <span>•</span>
                <span>Thứ 7, 13/06/2026</span>
            </span>
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 8px; width: 40%;">
                    <img src="https://flagcdn.com/w40/us.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                    <span style="font-weight: 500; font-size: 13px;">Mỹ</span>
                </div>
                <div style="width: 20%; text-align: center; font-weight: bold; font-size: 13px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">
                    <span>08:00</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px; justify-content: flex-end; width: 40%;">
                    <span style="font-weight: 500; font-size: 13px;">Paraguay</span>
                    <img src="https://flagcdn.com/w40/py.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                </div>
            </div>
        </a>
        <a class="wc2026-schedule-home-item__inner" href="https://znews.vn/worldcup-2026/qatar-vs-thuy-si-tran-dau-513496.html" style="display: block; text-decoration: none; color: inherit; margin-top: 12px; border-top: 1px solid #f1f5f9; padding-top: 12px;">
            <span style="display: flex; gap: 8px; font-size: 11px; color: #888; margin-bottom: 4px;">
                <span>Bảng B</span>
                <span>•</span>
                <span>Chủ nhật, 14/06/2026</span>
            </span>
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 8px; width: 40%;">
                    <img src="https://flagcdn.com/w40/qa.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                    <span style="font-weight: 500; font-size: 13px;">Qatar</span>
                </div>
                <div style="width: 20%; text-align: center; font-weight: bold; font-size: 13px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">
                    <span>02:00</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px; justify-content: flex-end; width: 40%;">
                    <span style="font-weight: 500; font-size: 13px;">Thụy Sĩ</span>
                    <img src="https://flagcdn.com/w40/ch.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                </div>
            </div>
        </a>
        <a class="wc2026-schedule-home-item__inner" href="https://znews.vn/worldcup-2026/brazil-vs-ma-roc-tran-dau-513499.html" style="display: block; text-decoration: none; color: inherit; margin-top: 12px; border-top: 1px solid #f1f5f9; padding-top: 12px;">
            <span style="display: flex; gap: 8px; font-size: 11px; color: #888; margin-bottom: 4px;">
                <span>Bảng C</span>
                <span>•</span>
                <span>Chủ nhật, 14/06/2026</span>
            </span>
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 8px; width: 40%;">
                    <img src="https://flagcdn.com/w40/br.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                    <span style="font-weight: 500; font-size: 13px;">Brazil</span>
                </div>
                <div style="width: 20%; text-align: center; font-weight: bold; font-size: 13px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">
                    <span>05:00</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px; justify-content: flex-end; width: 40%;">
                    <span style="font-weight: 500; font-size: 13px;">Ma Rốc</span>
                    <img src="https://flagcdn.com/w40/ma.png" style="width: 20px; height: 14px; object-fit: cover; border-radius: 2px;" />
                </div>
            </div>
        </a>
    `;
}
