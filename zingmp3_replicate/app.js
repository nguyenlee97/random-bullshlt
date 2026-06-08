/**
 * ZingMP3 Replicate Main Application Script
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('[ZingMP3-App] Initializing mock ad integration...');
    
    // Initialize the top ad banner
    initAdSlot('ZingMP3_Masthead');
});

/**
 * Initializes an ad slot, displaying a spinner, fetching the ad content,
 * and rendering it with close buttons and badges.
 * @param {string} zoneId - The ID of the ad slot
 */
function initAdSlot(zoneId) {
    const container = document.getElementById(zoneId);
    if (!container) {
        console.warn(`[ZingMP3-App] Ad container with ID "${zoneId}" not found in DOM.`);
        return;
    }

    // 1. Show loading spinner
    container.innerHTML = '<div class="ad-spinner"></div>';
    
    // 2. Fetch ad content from mock API client
    AdsPilotClient.checkAd(zoneId)
        .then(ad => {
            // Simulate brief network delay for visual smoothness
            setTimeout(() => {
                if (ad && ad.hasAd) {
                    renderAd(container, ad);
                } else {
                    console.log(`[ZingMP3-App] No active ad for ${zoneId}. Hiding container.`);
                    container.style.display = 'none';
                }
            }, 600);
        })
        .catch(err => {
            console.error(`[ZingMP3-App] Failed to load ad for ${zoneId}:`, err);
            container.style.display = 'none';
        });
}

/**
 * Renders the ad HTML inside the container and appends the close button and badge.
 * @param {HTMLElement} container - The banner wrapper element
 * @param {object} ad - The ad payload object
 */
function renderAd(container, ad) {
    // Clear spinner
    container.innerHTML = '';
    
    // Create the content wrapper
    const contentWrapper = document.createElement('div');
    contentWrapper.style.width = '100%';
    contentWrapper.style.height = '100%';
    contentWrapper.innerHTML = ad.html;
    container.appendChild(contentWrapper);
    
    // Create Close Button
    const closeBtn = document.createElement('button');
    closeBtn.className = 'ad-close-btn';
    closeBtn.innerHTML = '&times;';
    closeBtn.title = 'Đóng quảng cáo';
    closeBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        closeAd(container);
    });
    container.appendChild(closeBtn);
    
    // Create Ad Badge
    const badge = document.createElement('div');
    badge.className = 'ad-badge';
    badge.innerText = 'Quảng cáo';
    container.appendChild(badge);
    
    // Mark as loaded for styling transitions
    container.classList.add('ad-loaded');
}

/**
 * Closes the ad banner with a smooth collapse transition.
 * @param {HTMLElement} container - The banner wrapper element
 */
function closeAd(container) {
    console.log('[ZingMP3-App] Closing ad banner...');
    
    // Animate transition (collapse height and fade out)
    container.style.opacity = '0';
    container.style.transform = 'scale(0.95)';
    
    setTimeout(() => {
        container.style.display = 'none';
        
        // Optionally hide the parent zmp3_Top container to reclaim vertical space
        const parent = document.getElementById('zmp3_Top');
        if (parent) {
            parent.style.display = 'none';
        }
    }, 300);
}
