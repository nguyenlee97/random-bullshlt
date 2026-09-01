const mongoose = require('mongoose');

const campaignReportStateSchema = new mongoose.Schema({
  campaignId: { type: String, required: true, unique: true, index: true },
  baselineRevision: { type: Number, default: 1 },
  activeRevision: { type: Number, default: 1 },
  nextRevision: { type: Number, default: 1 },
  activeInputHash: { type: String, default: '' },
  activeScenario: { type: mongoose.Schema.Types.Mixed, default: null },
  leaseToken: { type: String },
  leaseUntil: { type: Date },
  appliedRequests: { type: mongoose.Schema.Types.Mixed, default: {} },
}, {
  collection: 'campaign_report_states',
  timestamps: true,
});

module.exports = mongoose.model('CampaignReportState', campaignReportStateSchema);
