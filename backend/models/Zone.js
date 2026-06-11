const mongoose = require('mongoose');

// ── Placement sub-schema ──────────────────────────────────────────────────────
const placementSchema = new mongoose.Schema(
  {
    id:      { type: String, required: true, unique: true },
    channel: { type: String, required: true },
    format:  { type: String, required: true },  // banner | native | video-vertical | audio | carousel | story-image | story-video | interstitial | rewarded-video
    size:    { type: String, required: true },   // e.g. "300x250" or "audio-30s"
    reach:   { type: Number, default: 0 },
    vi:      { type: Number, default: 0 },       // viewable impression %
    ctr:     { type: Number, default: 0 },       // CTR %
    cpm:     { type: Number, default: 0 },       // CPM in VND per 1000 imp
    obj:     { type: String, default: '' },      // best-fit objective
    // Extra validation metadata (added for zone-validation warnings)
    testSiteZone: { type: String, default: null }, // if this maps to a real test site zone id
    siteId:       { type: String, default: null }, // 'znews' | 'baomoi' | 'zingmp3'
  },
  { _id: false }
);

// ── Channel sub-schema ────────────────────────────────────────────────────────
const channelSchema = new mongoose.Schema(
  {
    id:    { type: String, required: true },
    name:  { type: String, required: true },
    reach: { type: Number, default: 0 },
  },
  { _id: false }
);

// ── Group sub-schema ──────────────────────────────────────────────────────────
const groupSchema = new mongoose.Schema(
  {
    id:       { type: String, required: true },
    name:     { type: String, required: true },
    desc:     { type: String, default: '' },
    channels: [{ type: String }],
  },
  { _id: false }
);

// ── Top-level Zone catalogue ──────────────────────────────────────────────────
const zoneCatalogSchema = new mongoose.Schema(
  {
    // Single document store: { groups: [...], channels: {...}, placements: [...] }
    groups:     [groupSchema],
    channels:   { type: mongoose.Schema.Types.Mixed, default: {} },
    placements: [placementSchema],
  },
  { collection: 'zones', timestamps: true }
);

module.exports = mongoose.model('ZoneCatalog', zoneCatalogSchema);
