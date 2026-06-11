// ─────────────────────────────────────────────────────────────────────────────
// Zone Validation Helper
// Returns an array of warning strings (never blocks the request).
// Called at campaign create/update time.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Validate a creative against the placements it targets.
 * @param {string[]} placementIds  - placement IDs from the order
 * @param {{ size: string }} creative - creative object {size: "720x1280"}
 * @param {object[]} allPlacements - full placements array from zone catalog
 * @returns {string[]} warnings
 */
function validatePlacements(placementIds, creative, allPlacements) {
  const warnings = [];

  if (!placementIds || !placementIds.length) return warnings;

  for (const pid of placementIds) {
    const placement = allPlacements.find((p) => p.id === pid);

    if (!placement) {
      warnings.push(`Placement "${pid}" not found in zone catalog.`);
      continue;
    }

    // Size mismatch check
    if (creative && creative.size && placement.size && placement.size !== 'audio-30s') {
      if (creative.size !== placement.size) {
        warnings.push(
          `Zone "${pid}" expects ${placement.size} ${placement.format}, but creative size is ${creative.size}.`
        );
      }
    }

    // Format-specific checks
    if (placement.format === 'video-vertical' && creative && creative.size) {
      const [w, h] = creative.size.split('x').map(Number);
      if (!isNaN(w) && !isNaN(h) && w >= h) {
        warnings.push(
          `Zone "${pid}" is a vertical video placement (portrait format). Creative "${creative.size}" appears to be landscape or square.`
        );
      }
    }

    if (placement.format === 'audio' && creative && creative.size && creative.size !== 'audio-30s') {
      warnings.push(
        `Zone "${pid}" is an audio placement. Creative size "${creative.size}" may be ignored; provide audio asset instead.`
      );
    }
  }

  return warnings;
}

module.exports = { validatePlacements };
