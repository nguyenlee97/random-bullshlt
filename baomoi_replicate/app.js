/**
 * BaoMoi Replicate - Ads & Scroll Interaction Manager
 */

const AD_ZONES = {
    background: 'BaoMoi_Background',
    masthead: 'BaoMoi_Masthead',
    stickyLeft: 'BaoMoi_StickyLeft',
    stickyRight: 'BaoMoi_StickyRight',
    box1: 'BaoMoi_Box1',
    box2: 'BaoMoi_Box2'
};

// State to keep track of closed ads
const adState = {
    stickyLeftClosed: false,
    stickyRightClosed: false,
    box2Loaded: false
};

document.addEventListener("DOMContentLoaded", () => {
    console.log("[AdAgent] BaoMoi page loaded. Initializing ad managers...");

    // 1. Initialize Background Ad & Gutter Click (and coordinate Masthead)
    initBackgroundAd();

    // 2. Initialize First Sidebar Ad
    initAdSlot(AD_ZONES.box1);

    // 3. Preload Sticky Side Banners (hidden by default)
    preloadStickyAds();

    // 4. Initialize Scroll Listeners
    setupScrollListeners();
});

/**
 * Initialize the background zone ad
 */
async function initBackgroundAd() {
    const bgData = await fetchAdForZone(AD_ZONES.background);
    const mastheadEl = document.getElementById(AD_ZONES.masthead);

    if (bgData && bgData.hasAd) {
        document.body.classList.add("has-bg-ad");
        document.body.style.backgroundImage = `url('${bgData.imageUrl}')`;
        
        const bgContainer = document.getElementById(AD_ZONES.background);
        if (bgContainer) {
            // Inject top gap link overlay and main background ad redirect HTML
            bgContainer.innerHTML = `
                <a href="${bgData.targetUrl}" target="_blank" class="baomoi-bg-top-link"></a>
                ${bgData.html}
            `;
            // Add gutter click handlers
            bgContainer.addEventListener("click", (e) => {
                // If clicked directly on the gutter overlay
                if (e.target === bgContainer) {
                    window.open(bgData.targetUrl, "_blank");
                }
            });
        }

        console.log("[AdAgent] Unified Skin mode active. Masthead banner hidden, top gap made clickable.");
    } else {
        // Fallback to loading independent masthead banner ad
        console.log("[AdAgent] Background skin not present. Loading standalone Masthead banner.");
        initAdSlot(AD_ZONES.masthead);
    }
}

/**
 * Standard loader and mounter for standard inline/masthead/sidebar zones
 */
function initAdSlot(zoneId) {
    const el = document.getElementById(zoneId);
    if (!el) return;

    el.innerHTML = `
        <div class="ad-loader">
            <div class="spinner"></div>
            <span>Đang tải quảng cáo...</span>
        </div>
    `;

    fetchAdForZone(zoneId).then(adData => {
        if (adData && adData.hasAd && adData.html) {
            el.innerHTML = adData.html;
            el.classList.add("loaded");
            bindCloseHandler(el);
            console.log(`[AdAgent] Ad successfully loaded inside #${zoneId}`);
        } else {
            el.innerHTML = "";
            el.classList.add("collapsed");
        }
    });
}

/**
 * Preload the sticky side ads so they are ready to fade in
 */
function preloadStickyAds() {
    // Left Sticky
    const leftEl = document.getElementById(AD_ZONES.stickyLeft);
    if (leftEl) {
        fetchAdForZone(AD_ZONES.stickyLeft).then(adData => {
            if (adData && adData.hasAd && adData.html) {
                leftEl.innerHTML = adData.html;
                bindCloseHandler(leftEl, () => {
                    adState.stickyLeftClosed = true;
                    leftEl.classList.remove("visible");
                });
            }
        });
    }

    // Right Sticky
    const rightEl = document.getElementById(AD_ZONES.stickyRight);
    if (rightEl) {
        fetchAdForZone(AD_ZONES.stickyRight).then(adData => {
            if (adData && adData.hasAd && adData.html) {
                rightEl.innerHTML = adData.html;
                bindCloseHandler(rightEl, () => {
                    adState.stickyRightClosed = true;
                    rightEl.classList.remove("visible");
                });
            }
        });
    }
}

/**
 * Attach click listener to the close 'x' button inside an ad container
 */
function bindCloseHandler(containerEl, customCallback = null) {
    const closeBtn = containerEl.querySelector(".ad-close-btn");
    if (!closeBtn) return;

    closeBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        console.log(`[AdAgent] Close clicked for ad container #${containerEl.id}`);
        
        if (customCallback) {
            customCallback();
        } else {
            containerEl.classList.add("collapsed");
        }
    });
}

/**
 * Handle scroll transitions:
 * 1. Sticky side ads appear after 300px of scroll
 * 2. Box2 (second sidebar ad) is injected after scrolling past 1500px
 */
function setupScrollListeners() {
    const stickyLeft = document.getElementById(AD_ZONES.stickyLeft);
    const stickyRight = document.getElementById(AD_ZONES.stickyRight);
    const box2 = document.getElementById(AD_ZONES.box2);

    window.addEventListener("scroll", () => {
        const scrollY = window.scrollY;

        // A. Handle Sticky Side Banners (fade-in after 300px)
        if (scrollY > 300) {
            if (stickyLeft && !adState.stickyLeftClosed) {
                stickyLeft.classList.add("visible");
            }
            if (stickyRight && !adState.stickyRightClosed) {
                stickyRight.classList.add("visible");
            }
        } else {
            if (stickyLeft) stickyLeft.classList.remove("visible");
            if (stickyRight) stickyRight.classList.remove("visible");
        }

        // B. Handle Box2 Sidebar Ad (lazy-injected after 1500px scroll)
        if (scrollY > 1500 && !adState.box2Loaded && box2) {
            adState.box2Loaded = true;
            console.log("[AdAgent] Scroll reached 1500px+. Loading dynamic sidebar ad #BaoMoi_Box2...");
            initAdSlot(AD_ZONES.box2);
        }
    });
}
