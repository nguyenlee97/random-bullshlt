'use strict';

const crypto = require('node:crypto');
const AnalyticsRecord = require('../models/AnalyticsRecord');
const ReportAnalysis = require('../models/ReportAnalysis');
const ReportDataset = require('../models/ReportDataset');
const CampaignReportState = require('../models/CampaignReportState');
const { PRESETS, applyScenario, expectationFor } = require('../lib/reportScenarios');

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
  const baseline = existing || await ReportDataset.findOneAndUpdate(
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
    CampaignReportState.findOne({ campaignId }, { _id: 0, __v: 0, leaseToken: 0 }).lean(),
    ReportDataset.find({ campaignId }, {
      _id: 0, __v: 0, records: 0, input: 0, analyses: 0, runtimeFixture: 0,
    }).sort({ revision: -1 }).limit(30).lean(),
  ]);
  const baseline = await ReportDataset.findOne({ campaignId, kind: 'baseline' }).lean();
  return { campaignId, presets: PRESETS, state, revisions,
    placements: [...new Set((baseline?.records || []).map(row => row.placementId))] };
}

async function baselineFor(campaignId) {
  let baseline = await ReportDataset.findOne({ campaignId, kind: 'baseline' }).lean();
  if (baseline) {
    // Repair a baseline insert whose following state insert was interrupted.
    await CampaignReportState.updateOne({ campaignId }, { $setOnInsert: {
      campaignId, baselineRevision: 1, activeRevision: 1, nextRevision: 1,
      activeInputHash: baseline.inputHash, activeScenario: null,
    } }, { upsert: true });
    return baseline;
  }
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
  const state = await CampaignReportState.findOne({ campaignId }).lean();
  const active = await ReportDataset.findOne({ campaignId, revision: state.activeRevision }).lean();
  return {
    campaignId,
    baselineRevision: baseline.revision,
    scenario: result.config,
    records: result.records,
    beforeRecords: active?.records || baseline.records,
    activeRevision: state.activeRevision,
    expectation: expectationFor(result.config.presetId),
  };
}

async function buildAnalyses(input, records) {
  // Lazy import prevents a report-generator/model cycle during process boot.
  const {
    REPORT_TYPES, generateAnalysis, questionsForReport,
  } = require('./reportGenerator');
  return Promise.all(REPORT_TYPES.map(async reportType => {
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
    return {
        campaignId: input.campaignId, reportType,
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
    };
  }));
}

async function applyScenarioRevision(campaignId, config, createdBy = 'agent_ui') {
  const { requestId, expectedRevision } = config;
  if (!/^[A-Za-z0-9_-]{8,100}$/.test(requestId || '') || !Number.isInteger(expectedRevision)) {
    throw new Error('requestId and expectedRevision are required');
  }
  const baseline = await baselineFor(campaignId);
  const transformed = applyScenario(baseline.records, config);
  const requestHash = datasetHash(baseline.inputHash, expectedRevision, transformed.config);
  let previousRequest = await ReportDataset.findOne({ campaignId, requestId }).lean();
  if (previousRequest && previousRequest.requestHash !== requestHash) throw conflict('requestId reused with different parameters');
  const now = new Date(), leaseToken = crypto.randomUUID();
  const state = await CampaignReportState.findOneAndUpdate({ campaignId,
    $or: [{ leaseUntil: { $exists: false } }, { leaseUntil: { $lte: now } }],
  }, { $set: { leaseToken, leaseUntil: new Date(Date.now() + 10 * 60_000) } }, { new: true }).lean();
  if (!state) throw conflict('Another scenario is being applied; retry with the same requestId');
  try {
    // A competing request may have finished between the first lookup and lease acquisition.
    previousRequest = await ReportDataset.findOne({ campaignId, requestId }).lean();
    if (previousRequest && previousRequest.requestHash !== requestHash) throw conflict('requestId reused with different parameters');
    // A completed retry returns its original result even if a newer scenario exists.
    if (previousRequest && (previousRequest.status === 'published' || state.appliedRequests?.[requestId] === previousRequest.revision)) return scenarioResult(previousRequest, true);
    if (state.activeRevision !== expectedRevision) throw conflict('Dataset revision changed; preview again');
    let dataset = previousRequest;
    if (!dataset) {
      const allocation = await CampaignReportState.findOneAndUpdate({ campaignId, leaseToken }, { $inc: { nextRevision: 1 } }, { new: true }).lean();
      const revision = allocation.nextRevision;
      const inputHash = datasetHash(baseline.input.inputHash, revision, transformed.config);
      dataset = await ReportDataset.create({
        campaignId, revision, kind: 'scenario', input: { ...baseline.input, inputHash }, inputHash,
        scenario: transformed.config, requestId, requestHash, status: 'building', createdBy,
        runtimeFixture: transformed.runtimeFixture,
        records: transformed.records.map(row => ({ ...row, campaignId, inputHash, scenario: { ...row.scenario, revision } })),
      });
      dataset = dataset.toObject();
    }
    const analyses = dataset.analyses?.length === 6 ? dataset.analyses : await buildAnalyses(dataset.input, dataset.records);
    await ReportDataset.updateOne({ campaignId, revision: dataset.revision }, { $set: { analyses, status: 'ready' } });
    const published = await CampaignReportState.updateOne({ campaignId, leaseToken,
      leaseUntil: { $gt: new Date() }, activeRevision: expectedRevision,
    }, { $set: { activeRevision: dataset.revision, activeInputHash: dataset.inputHash, activeScenario: dataset.scenario,
      [`appliedRequests.${requestId}`]: dataset.revision } });
    if (published.modifiedCount !== 1) throw conflict('Scenario lease or dataset revision changed; retry');
    await ReportDataset.updateOne({ campaignId, revision: dataset.revision }, { $set: { status: 'published' } });
    return scenarioResult(dataset, false);
  } finally {
    await CampaignReportState.updateOne({ campaignId, leaseToken }, { $unset: { leaseToken: '', leaseUntil: '' } });
  }
}

function conflict(message) { const error = new Error(message); error.status = 409; return error; }
function scenarioResult(dataset, replayed) {
  return { campaignId: dataset.campaignId, revision: dataset.revision, inputHash: dataset.inputHash,
    scenario: dataset.scenario, expectation: expectationFor(dataset.scenario?.presetId),
    recordCount: dataset.records.length, replayed };
}

// The pointer is read once and the referenced records + analyses never mutate
// after publication. In-progress builds are invisible to report readers.
async function activeSnapshot(campaignId) {
  const state = await CampaignReportState.findOne({ campaignId }).lean();
  if (!state || state.activeRevision <= 1) return null;
  const dataset = await ReportDataset.findOne({ campaignId, revision: state.activeRevision }).lean();
  if (!dataset) throw conflict('Active report snapshot is missing; repair the dataset before reading reports');
  if (dataset.analyses?.length === 6) return dataset;
  // The first Evaluation release stored scenario prose only in the legacy
  // collection. Migrate it only when all six analyses match the pinned hash.
  if (!dataset.requestId) {
    const analyses = await ReportAnalysis.find({ campaignId, status: 'ready', inputHash: dataset.inputHash }).lean();
    if (analyses.length === 6) {
      await ReportDataset.updateOne({ campaignId, revision: dataset.revision, requestId: { $exists: false } },
        { $set: { analyses, status: 'published' } });
      return { ...dataset, analyses, status: 'published' };
    }
  }
  throw conflict('Active scenario analyses are incomplete; restore a complete dataset before reading reports');
}

async function activeRecords(campaignId) {
  const snapshot = await activeSnapshot(campaignId);
  return snapshot ? snapshot.records : AnalyticsRecord.find({ campaignId }).sort({ date: 1 }).lean();
}

async function activeAnalyses(campaignId) {
  const snapshot = await activeSnapshot(campaignId);
  return snapshot ? snapshot.analyses : ReportAnalysis.find({ campaignId }).lean();
}

module.exports = {
  ensureBaselineDataset, getScenarioWorkspace, previewScenario,
  applyScenarioRevision, cleanRecords, datasetHash,
  activeSnapshot, activeRecords, activeAnalyses, baselineFor, buildAnalyses,
};
