const express = require('express');
const router = express.Router();
const { getReportStatus } = require('../services/reportGenerator');
const ReportAnalysis = require('../models/ReportAnalysis');
const AnalyticsRecord = require('../models/AnalyticsRecord');
const { launchReportGeneration } = require('../services/reportLauncher');
const {
  getScenarioWorkspace, previewScenario, applyScenarioRevision, activeSnapshot, activeRecords, activeAnalyses, baselineFor,
} = require('../services/reportDatasets');

function requireInternalReportAccess(req, res, next) {
  const expected = process.env.REPORT_INTERNAL_API_KEY || '';
  if (!expected) return res.status(503).json({ error: 'report internal API is not configured' });
  if (req.get('x-report-internal-key') !== expected) {
    return res.status(401).json({ error: 'report internal API access denied' });
  }
  next();
}

router.get('/internal/scenarios/:campaignId', requireInternalReportAccess, async (req, res) => {
  try {
    await baselineFor(req.params.campaignId);
    res.set('Cache-Control', 'no-store');
    res.json(await getScenarioWorkspace(req.params.campaignId));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.get('/internal/datasets/:campaignId', requireInternalReportAccess, async (req, res) => {
  try {
    await baselineFor(req.params.campaignId);
    const ReportDataset = require('../models/ReportDataset');
    const CampaignReportState = require('../models/CampaignReportState');
    const state = await CampaignReportState.findOne({ campaignId: req.params.campaignId }).lean();
    if (!state) return res.status(404).json({ error: 'report dataset not found' });
    const [baseline, active] = await Promise.all([
      ReportDataset.findOne({ campaignId: req.params.campaignId, revision: state.baselineRevision }).lean(),
      ReportDataset.findOne({ campaignId: req.params.campaignId, revision: state.activeRevision }).lean(),
    ]);
    res.set('Cache-Control', 'no-store');
    const { leaseToken, appliedRequests, ...publicState } = state;
    res.json({ campaignId: req.params.campaignId, state: publicState, baseline, active });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.post('/internal/scenarios/:campaignId/preview', requireInternalReportAccess, async (req, res) => {
  try {
    res.json(await previewScenario(req.params.campaignId, req.body || {}));
  } catch (err) {
    res.status(err.status || (err.code === 'REPORT_BASELINE_NOT_READY' ? 409 : 400)).json({ error: err.message });
  }
});

router.post('/internal/scenarios/:campaignId/apply', requireInternalReportAccess, async (req, res) => {
  try {
    const result = await applyScenarioRevision(
      req.params.campaignId, req.body || {}, req.body?.createdBy || 'agent_ui',
    );
    res.json(result);
  } catch (err) {
    res.status(err.status || (err.code === 'REPORT_BASELINE_NOT_READY' ? 409 : 400)).json({ error: err.message });
  }
});

// ── POST /api/reports/generate ───────────────────────────────────────────────
// Trigger report generation for a campaign. Idempotent — skips if already generating/ready.
// Body: complete report-input-v2 campaign snapshot. Legacy reports are kept
// read-only unless an operator explicitly requests an upgrade.
router.post('/generate', async (req, res) => {
  try {
    const result = await launchReportGeneration(req.body || {});
    res.json(result);
  } catch (err) {
    if (err.message === 'campaignId required') return res.status(400).json({ error: err.message });
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/reports/status/:campaignId ──────────────────────────────────────
// Poll generation status — must never be cached (browser would get stale "pending")
router.get('/status/:campaignId', async (req, res) => {
  try {
    res.set('Cache-Control', 'no-store, no-cache, must-revalidate');
    res.set('Pragma', 'no-cache');
    const snapshot = await activeSnapshot(req.params.campaignId);
    const status = snapshot ? {
      campaignId: req.params.campaignId, total: 6, ready: 6, errors: 0, contractReady: 6,
      revision: snapshot.revision, inputHash: snapshot.inputHash,
      types: Object.fromEntries(snapshot.analyses.map(doc => [doc.reportType, 'ready'])),
    } : await getReportStatus(req.params.campaignId);
    res.json(status);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/reports/analysis/:campaignId ────────────────────────────────────
// Fetch all analyses for a campaign
router.get('/analysis/:campaignId', async (req, res) => {
  try {
    const docs = (await activeAnalyses(req.params.campaignId)).filter(doc => doc.status === 'ready');
    res.json(docs);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/reports/analysis/:campaignId/:reportType ────────────────────────
// Fetch single report type analysis
router.get('/analysis/:campaignId/:reportType', async (req, res) => {
  try {
    const doc = (await activeAnalyses(req.params.campaignId)).find(doc => doc.reportType === req.params.reportType);
    if (!doc) return res.status(404).json({ error: 'not found' });
    res.json(doc);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/reports/data/:campaignId ────────────────────────────────────────
// Fetch raw analytics records for a campaign (convenience wrapper)
router.get('/data/:campaignId', async (req, res) => {
  try {
    const records = await activeRecords(req.params.campaignId);
    res.json(records);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/reports/debug/:campaignId ───────────────────────────────────────
// Debug endpoint: shows record count, samples, and analysis errors
router.get('/debug/:campaignId', async (req, res) => {
  try {
    const { campaignId } = req.params;

    // Records summary
    const recordCount = await AnalyticsRecord.countDocuments({ campaignId });
    const sampleRecords = await AnalyticsRecord.find({ campaignId })
      .sort({ date: 1 }).limit(3).lean();

    // Check if any records have real data
    const nonZeroRecords = await AnalyticsRecord.countDocuments({
      campaignId,
      impressions: { $gt: 0 },
    });

    // Totals
    const agg = await AnalyticsRecord.aggregate([
      { $match: { campaignId } },
      { $group: {
        _id: null,
        totalImpressions: { $sum: '$impressions' },
        totalClicks: { $sum: '$clicks' },
        totalSpend: { $sum: '$spend' },
        totalConversions: { $sum: '$conversions' },
      }},
    ]);

    // Analysis docs with error info
    const analyses = await ReportAnalysis.find(
      { campaignId },
      { _id: 0, reportType: 1, status: 1, error: 1, generatedAt: 1, 'questions.0': 1 }
    ).lean();

    res.json({
      campaignId,
      records: {
        total: recordCount,
        withData: nonZeroRecords,
        withZeros: recordCount - nonZeroRecords,
        totals: agg[0] || { totalImpressions: 0, totalClicks: 0, totalSpend: 0, totalConversions: 0 },
        samples: sampleRecords.map(r => ({
          date: r.date, placementId: r.placementId,
          impressions: r.impressions, clicks: r.clicks, spend: r.spend,
        })),
      },
      analyses: analyses.map(a => ({
        reportType: a.reportType,
        status: a.status,
        error: a.error || null,
        generatedAt: a.generatedAt,
        hasFirstQuestion: !!(a.questions?.[0]),
      })),
      diagnosis: recordCount === 0
        ? '❌ No records — Phase 1 (data generation) failed or never ran'
        : nonZeroRecords === 0
        ? '❌ Records exist but all zeros — OpenAI returned empty/zero data'
        : '✅ Records look healthy',
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});


// ── POST /api/reports/send-email/:campaignId ─────────────────────────────────
// Generate PDF + send via Resend. Body: { email, cc?, attachCsv?, attachJson? }
router.post('/send-email/:campaignId', async (req, res) => {
  try {
    const { campaignId } = req.params;
    const { email, cc, attachCsv = false, attachJson = false } = req.body;

    if (!email) return res.status(400).json({ error: 'email required' });

    const { generatePDF } = require('../services/reportPDFGenerator');
    const { sendCampaignReport } = require('../services/emailService');

    // Pin one snapshot for the whole email/PDF package.
    const snapshot = await activeSnapshot(campaignId);
    const records = snapshot ? snapshot.records : await activeRecords(campaignId);
    const totals = records.reduce((acc, r) => {
      acc.impressions  += r.impressions  || 0;
      acc.clicks       += r.clicks       || 0;
      acc.spend        += r.spend        || 0;
      acc.conversions  += r.conversions  || 0;
      acc.reach        += r.reach        || 0;
      return acc;
    }, { impressions: 0, clicks: 0, spend: 0, conversions: 0, reach: 0 });

    // Fetch executive summary text for email body
    const execAnalysis = (snapshot ? snapshot.analyses : await activeAnalyses(campaignId)).find(doc => doc.reportType === 'executive' && doc.status === 'ready');
    const overallText = execAnalysis?.overall || '';
    const brand     = execAnalysis?.brand     || campaignId;
    const objective = execAnalysis?.objective || 'awareness';

    // Generate PDF
    console.log(`[send-email] Generating PDF for ${campaignId}...`);
    const pdfBuffer = await generatePDF(campaignId, snapshot);

    // Send email
    const result = await sendCampaignReport({
      to: email, cc,
      campaignId, brand, objective,
      totals, overallText,
      pdfBuffer,
      attachCsv, attachJson,
      records: (attachCsv || attachJson) ? records : [],
    });

    res.json({ ok: true, messageId: result.messageId, to: email });
  } catch (err) {
    console.error('[send-email] Error:', err.message);
    if (err.code === 'REPORT_NOT_READY') {
      return res.status(409).json({ error: err.message, missingTypes: err.missingTypes || [] });
    }
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/reports/export/:campaignId/pdf ───────────────────────────────────
// Download PDF directly from browser (no email)
router.get('/export/:campaignId/pdf', async (req, res) => {
  try {
    const { campaignId } = req.params;
    const { generatePDF } = require('../services/reportPDFGenerator');
    const buf = await generatePDF(campaignId);
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Content-Disposition', `attachment; filename="report_${campaignId}.pdf"`);
    res.send(buf);
  } catch (err) {
    if (err.code === 'REPORT_NOT_READY') {
      return res.status(409).json({ error: err.message, missingTypes: err.missingTypes || [] });
    }
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/reports/export/:campaignId/csv ───────────────────────────────────
router.get('/export/:campaignId/csv', async (req, res) => {
  try {
    const { campaignId } = req.params;
    const records = await activeRecords(campaignId);
    const cols = ['campaignId','placementId','channel','format','date',
      'impressions','clicks','reach','spend','conversions','vi','ctr','cpm'];
    const rows = records.map(r => cols.map(h => {
      const v = r[h] ?? '';
      return typeof v === 'string' && v.includes(',') ? `"${v}"` : v;
    }).join(','));
    const csv = [cols.join(','), ...rows].join('\n');
    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', `attachment; filename="analytics_${campaignId}.csv"`);
    res.send(csv);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/reports/export/:campaignId/json ──────────────────────────────────
router.get('/export/:campaignId/json', async (req, res) => {
  try {
    const { campaignId } = req.params;
    const records = await activeRecords(campaignId);
    res.setHeader('Content-Disposition', `attachment; filename="analytics_${campaignId}.json"`);
    res.json(records);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
