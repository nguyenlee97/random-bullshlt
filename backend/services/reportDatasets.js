'use strict';

const crypto = require('node:crypto');
const AnalyticsRecord = require('../models/AnalyticsRecord');
const ReportAnalysis = require('../models/ReportAnalysis');
const ReportDataset = require('../models/ReportDataset');
const CampaignReportState = require('../models/CampaignReportState');
const { PRESETS, applyScenario } = require('../lib/reportScenarios');

function cleanRecords(records) {
  return (records || []).map(value => {
    const row = typeof value.toObject === 'function' ? value.toObject() : { ...value };
    delete row._id;
    delete row.__v;
    delete row.createdAt;
    delete row.updatedAt;
    return row;
  });
}

function datasetHash(inputHash, revision, scenario) {
  return crypto.createHash('sha256').update(JSON.stringify({
    inputHash, revision, scenario,
  })).digest('hex');
}

async function ensureBaselineDataset(input, recordsValue) {
  const records = cleanRecords(recordsValue);
  const campaignId = String(input.campaignId);
  const existing = await ReportDataset.findOne({ campaignId, kind: 'baseline' }).lean();
  if (existing) return existing;
  const baseline = await ReportDataset.findOneAndUpdate(
    { campaignId, revision: 1 },
    { $setOnInsert: {
      campaignId, revision: 1, kind: 'baseline', input,
      inputHash: input.inputHash, scenario: null, records, createdBy: 'report_generator',
    } },
    { upsert: true, new: true },
  ).lean();
  await CampaignReportState.findOneAndUpdate(
    { campaignId },
    { $setOnInsert: {
      campaignId, baselineRevision: 1, activeRevision: 1, nextRevision: 1,
      activeInputHash: input.inputHash, activeScenario: null,
    } },
    { upsert: true },
  );
  return baseline;
}

async function getScenarioWorkspace(campaignId) {
  const [state, revisions] = await Promise.all([
    CampaignReportState.findOne({ campaignId }, { _id: 0, __v: 0 }).lean(),
    ReportDataset.find({ campaignId }, {
      _id: 0, __v: 0, records: 0, input: 0,
    }).sort({ revision: -1 }).limit(30).lean(),
  ]);
  return { campaignId, presets: PRESETS, state, revisions };
}

async function baselineFor(campaignId) {
  let baseline = await ReportDataset.findOne({ campaignId, kind: 'baseline' }).lean();
  if (baseline) return baseline;
  const analysis = await ReportAnalysis.findOne({ campaignId, inputHash: { $ne: '' } }).lean();
  const records = await AnalyticsRecord.find({ campaignId }).sort({ date: 1 }).lean();
  let input = analysis?.provenance?.reportInput || analysis?.pendingInput;
  if (!input) {
    const Campaign = require('../models/Campaign');
    const { normalizeReportInput } = require('../lib/reportMeasurement');
    const order = await Campaign.findOne({ orderId: campaignId, deletedAt: null }).lean();
    if (order) {
      input = normalizeReportInput({
        campaignId, brand: order.brand, objective: order.objective,
        budget: order.budget, startDate: order.startDate, endDate: order.endDate,
        zones: order.placements || [], targeting: order.targeting || {},
        creative: { primary: order.creative || {}, files: order.creatives || [] },
      });
      if (analysis?.inputHash) input = { ...input, inputHash: analysis.inputHash };
    }
  }
  if (!input || !records.length) {
    const error = new Error('baseline report dataset is not available');
    error.code = 'REPORT_BASELINE_NOT_READY';
    throw error;
  }
  baseline = await ensureBaselineDataset(input, records);
  return baseline;
}

async function previewScenario(campaignId, config) {
  const baseline = await baselineFor(campaignId);
  const result = applyScenario(baseline.records, config);
  return {
    campaignId,
    baselineRevision: baseline.revision,
    scenario: result.config,
    records: result.records,
  };
}

async function rebuildAnalyses(input, records) {
  // Lazy import prevents a report-generator/model cycle during process boot.
  const {
    REPORT_TYPES, generateAnalysis, questionsForReport,
  } = require('./reportGenerator');
  await Promise.all(REPORT_TYPES.map(async reportType => {
    const result = await generateAnalysis(input, records, reportType);
    const questions = questionsForReport(reportType, result.dataContract).map(question => {
      const answered = (result.questions || []).find(item => item.id === question.id);
      return {
        ...question,
        findingIds: answered?.findingIds || [],
        answer: answered?.answer || {
          sections: [{ type: 'summary', text: 'Chưa có phân tích cho câu hỏi này.' }],
        },
      };
    });
    await ReportAnalysis.findOneAndUpdate(
      { campaignId: input.campaignId, reportType },
      { $set: {
        status: 'ready', overall: result.overall || '', questions,
        dataContract: result.dataContract, inputHash: input.inputHash,
        schemaVersion: result.dataContract.contractVersion,
        performanceStatus: result.dataContract.performanceStatus,
        actions: result.dataContract.actions,
        provenance: {
          provider: result.analysisProvenance?.provider || 'deterministic_fallback',
          model: result.analysisProvenance?.model || 'none',
          schema: 'report-evidence-v2', source: 'scenario_simulation',
          inputHash: input.inputHash, reportInput: input,
          fallbackReason: result.analysisProvenance?.reason || null,
        },
        generatedAt: new Date(), error: '', pendingInput: null,
      } },
      { upsert: true },
    );
  }));
}

async function applyScenarioRevision(campaignId, config, createdBy = 'agent_ui') {
  const baseline = await baselineFor(campaignId);
  const transformed = applyScenario(baseline.records, config);
  const state = await CampaignReportState.findOneAndUpdate(
    { campaignId },
    { $inc: { nextRevision: 1 } },
    { new: true, upsert: true, setDefaultsOnInsert: true },
  ).lean();
  const revision = state.nextRevision;
  const inputHash = datasetHash(baseline.input.inputHash, revision, transformed.config);
  const input = { ...baseline.input, inputHash };
  const records = transformed.records.map(row => ({
    ...row, campaignId, inputHash,
    scenario: { ...(row.scenario || {}), revision },
  }));
  await ReportDataset.create({
    campaignId, revision, kind: 'scenario', input, inputHash,
    scenario: transformed.config, records, createdBy,
  });

  const previous = await ReportDataset.findOne({
    campaignId, revision: state.activeRevision,
  }).lean();
  try {
    await AnalyticsRecord.deleteMany({ campaignId });
    await AnalyticsRecord.insertMany(records);
    await rebuildAnalyses(input, records);
    await CampaignReportState.updateOne({ campaignId }, { $set: {
      activeRevision: revision, activeInputHash: inputHash,
      activeScenario: transformed.config,
    } });
  } catch (error) {
    if (previous?.records?.length) {
      await AnalyticsRecord.deleteMany({ campaignId });
      await AnalyticsRecord.insertMany(cleanRecords(previous.records));
      await rebuildAnalyses(previous.input, cleanRecords(previous.records));
    }
    await ReportDataset.updateOne(
      { campaignId, revision },
      { $set: { 'scenario.applyError': error.message } },
    );
    throw error;
  }
  return {
    campaignId, revision, inputHash, scenario: transformed.config,
    recordCount: records.length,
  };
}

module.exports = {
  ensureBaselineDataset, getScenarioWorkspace, previewScenario,
  applyScenarioRevision, cleanRecords, datasetHash,
};
