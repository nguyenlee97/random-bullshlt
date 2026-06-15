// ─────────────────────────────────────────────────────────────────────────────
// Zone Validation Helper
// Returns an array of warning strings (never blocks the request).
// Called at campaign create/update time.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Find the best-matched creative for a given zone, using same priority as ads.js:
 *   1. zones[] explicit match (zone-specific)
 *   2. size match
 *   3. format match
 *   4. first creative (last resort)
 * @param {string} zoneId
 * @param {object[]} creatives - array of creative objects
 * @param {object} legacyCreative - fallback single creative
 * @returns {object|null}
 */
function matchCreativeForZone(zoneId, creatives, legacyCreative) {
  if (Array.isArray(creatives) && creatives.length) {
    // Priority 1: zone-specific
    const byZone = creatives.find(c => Array.isArray(c.zones) && c.zones.includes(zoneId));
    if (byZone) return byZone;
    // Priority 2: size match (done later with placement info)
    // Return null so caller can do size fallback with placement data
    return null;
  }
  return legacyCreative || null;
}

/**
 * Validate creatives against the placements they target.
 * Uses zone-specific creative matching before falling back to size comparison.
 *
 * @param {string[]}  placementIds    - placement IDs from the order
 * @param {object[]}  creatives       - creatives[] array (new multi-creative system)
 * @param {object}    legacyCreative  - legacy single creative fallback
 * @param {object[]}  allPlacements   - full placements array from zone catalog
 * @returns {string[]} warnings
 */
function validatePlacements(placementIds, legacyCreative, allPlacements, creatives) {
  const warnings = [];

  if (!placementIds || !placementIds.length) return warnings;

  for (const pid of placementIds) {
    const placement = allPlacements.find((p) => p.id === pid);

    if (!placement) {
      warnings.push(`Placement "${pid}" not found in zone catalog.`);
      continue;
    }

    // Flexible zones: accept any banner-format image without strict size check
    if (placement.flexible) continue;

    // Find the creative that will actually serve this zone
    let creative = null;

    if (Array.isArray(creatives) && creatives.length) {
      // Priority 1: zone-specific
      creative = creatives.find(c => Array.isArray(c.zones) && c.zones.includes(pid));
      // Priority 2: size match
      if (!creative && placement.size) {
        creative = creatives.find(c => c.size === placement.size);
      }
      // Priority 3: format match
      if (!creative && placement.format) {
        creative = creatives.find(c => c.format === placement.format);
      }
      // Priority 4: first creative
      if (!creative) creative = creatives[0];
    } else {
      creative = legacyCreative || null;
    }

    if (!creative || !creative.size) continue; // no creative to compare

    // Size mismatch check (skip audio zones)
    if (placement.size && placement.size !== 'audio-30s') {
      if (creative.size !== placement.size) {
        warnings.push(
          `Zone "${pid}" expects ${placement.size} ${placement.format}, but matched creative size is ${creative.size}.`
        );
      }
    }

    // Format-specific checks
    if (placement.format === 'video-vertical' && creative.size) {
      const [w, h] = creative.size.split('x').map(Number);
      if (!isNaN(w) && !isNaN(h) && w >= h) {
        warnings.push(
          `Zone "${pid}" is a vertical video placement (portrait format). Creative "${creative.size}" appears to be landscape or square.`
        );
      }
    }

    if (placement.format === 'audio' && creative.size && creative.size !== 'audio-30s') {
      warnings.push(
        `Zone "${pid}" is an audio placement. Creative size "${creative.size}" may be ignored; provide audio asset instead.`
      );
    }
  }

  return warnings;
}

module.exports = { validatePlacements };
