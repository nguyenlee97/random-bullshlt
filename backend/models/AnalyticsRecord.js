const mongoose = require('mongoose');

// Per-day analytics record per campaign per placement
const analyticsSchema = new mongoose.Schema(
  {
    campaignId:  { type: String, required: true, index: true },   // orderId
    placementId: { type: String, required: true, index: true },
    date:        { type: String, required: true, index: true },   // YYYY-MM-DD
    channel:     { type: String, default: '' },
    format:      { type: String, default: '' },
    impressions: { type: Number, default: 0 },
    clicks:      { type: Number, default: 0 },
    spend:       { type: Number, default: 0 },   // VND
    ctr:         { type: Number, default: 0 },   // %
    cpm:         { type: Number, default: 0 },   // VND per 1000
    reach:       { type: Number, default: 0 },   // unique users (estimated)
    conversions: { type: Number, default: 0 },
    // Viewability
    vi:          { type: Number, default: 0 },   // viewable impression %
  },
  {
    collection: 'analytics_records',
    timestamps: true,
  }
);

// Compound index for efficient date-range queries
analyticsSchema.index({ campaignId: 1, date: 1 });
analyticsSchema.index({ placementId: 1, date: 1 });

module.exports = mongoose.model('AnalyticsRecord', analyticsSchema);
