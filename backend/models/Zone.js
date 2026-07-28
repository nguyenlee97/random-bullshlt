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
    metricSource:  { type: String, default: null }, // provenance for synthetic/demo metrics
    inventoryTier: { type: String, default: null }, // comparable placement-value tier
    // Extra validation metadata (added for zone-validation warnings)
    testSiteZone: { type: String, default: null }, // if this maps to a real test site zone id
    siteId:       { type: String, default: null }, // 'znews' | 'baomoi' | 'zingmp3'
    siteUrl:      { type: String, default: null }, // direct URL to the test site page where this ad shows
    publisher:    { type: String, default: null },
    subFormat:    { type: String, default: null },
    flexible:     { type: Boolean, default: false },
    pageTemplate: { type: String, default: null },
    topicId:      { type: String, default: null },
    placementFamily:   { type: String, default: null },
    comparisonGroupId: { type: String, default: null },
    device:             [{ type: String }],
    creativeContractId: { type: String, default: null },
    catalogVersion:     { type: String, default: null },
    recordRevision:     { type: Number, default: 1 },
    lifecycleStatus:    { type: String, default: 'active' },
    renderer:           { type: mongoose.Schema.Types.Mixed, default: null },
    audienceContext:    { type: mongoose.Schema.Types.Mixed, default: null },
    provenance:         { type: mongoose.Schema.Types.Mixed, default: null },
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
    catalogVersion:    { type: String, default: 'legacy-35' },
    taxonomyVersion:   { type: String, default: null },
    revision:          { type: Number, default: 1 },
    previousVersion:   { type: String, default: null },
    creativeContracts: { type: [mongoose.Schema.Types.Mixed], default: [] },
    topicTaxonomy:     { type: [mongoose.Schema.Types.Mixed], default: [] },
  },
  { collection: 'zones', timestamps: true }
);

module.exports = mongoose.model('ZoneCatalog', zoneCatalogSchema);
