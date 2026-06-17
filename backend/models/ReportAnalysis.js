const mongoose = require('mongoose');

const questionSchema = new mongoose.Schema({
  id:       { type: String, required: true },
  question: { type: String, required: true },
  answer:   { type: mongoose.Schema.Types.Mixed },  // structured sections[]
  category: { type: String, default: 'performance' },
}, { _id: false });

const reportAnalysisSchema = new mongoose.Schema(
  {
    campaignId: { type: String, required: true, index: true },
    reportType: { type: String, required: true, index: true },
    status:     { type: String, default: 'generating', enum: ['generating', 'ready', 'error'] },
    overall:    { type: String, default: '' },
    questions:  [questionSchema],
    error:      { type: String, default: '' },
    generatedAt: { type: Date },
  },
  {
    collection: 'report_analyses',
    timestamps: true,
  }
);

reportAnalysisSchema.index({ campaignId: 1, reportType: 1 }, { unique: true });

module.exports = mongoose.model('ReportAnalysis', reportAnalysisSchema);
