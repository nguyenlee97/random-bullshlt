const mongoose = require('mongoose');

const reportDatasetSchema = new mongoose.Schema({
  campaignId: { type: String, required: true, index: true },
  revision: { type: Number, required: true },
  kind: { type: String, enum: ['baseline', 'scenario'], required: true },
  input: { type: mongoose.Schema.Types.Mixed, required: true },
  inputHash: { type: String, required: true, index: true },
  scenario: { type: mongoose.Schema.Types.Mixed, default: null },
  runtimeFixture: { type: mongoose.Schema.Types.Mixed, default: null },
  records: { type: [mongoose.Schema.Types.Mixed], default: [] },
  createdBy: { type: String, default: 'system' },
  requestId: { type: String },
  requestHash: { type: String },
  status: { type: String, default: 'ready' },
  analyses: { type: [mongoose.Schema.Types.Mixed], default: [] },
}, {
  collection: 'report_datasets',
  timestamps: true,
});

reportDatasetSchema.index({ campaignId: 1, revision: 1 }, { unique: true });
reportDatasetSchema.index({ campaignId: 1, requestId: 1 }, { unique: true, partialFilterExpression: { requestId: { $type: 'string' } } });

module.exports = mongoose.model('ReportDataset', reportDatasetSchema);
