const ReportAnalysis = require('../models/ReportAnalysis');
const { generateReports, REPORT_TYPES } = require('./reportGenerator');
const { hasActiveReportGeneration } = require('../lib/reportGenerationLease');
const { normalizeReportInput } = require('../lib/reportMeasurement');

const EVIDENCE_V2 = 'report-evidence-v2';


function inferReportZone(rawId) {
  const id = String(rawId || '');
  const lower = id.toLowerCase();
  if (lower.includes('baomoi') || lower.startsWith('bm')) {
    return { id, channel: 'BaoMoi', format: 'banner', cpm: 25000 };
  }
  if (lower.includes('zingmp3') || lower.includes('zmp3') || lower.includes('mp3')) {
    return { id, channel: 'ZingMP3', format: 'audio_banner', cpm: 22000 };
  }
  return { id, channel: 'Znews', format: 'banner', cpm: 28000 };
}

function inspectReportGeneration(docs, inputHash, allowLegacyUpgrade = false) {
  const legacyReady = docs.filter(doc => (
    doc.status === 'ready' && doc?.dataContract?.contractVersion !== EVIDENCE_V2
  ));
  if (legacyReady.length && !allowLegacyUpgrade) {
    return { action: 'preserve_legacy', legacyReady };
  }

  const readyForInput = docs.filter(doc => (
    doc.status === 'ready' && doc.schemaVersion === EVIDENCE_V2
      && doc.inputHash === inputHash
  )).length;
  if (readyForInput >= REPORT_TYPES.length) return { action: 'already_ready' };

  const generatingDocs = docs.filter(doc => doc.status === 'generating');
  if (!generatingDocs.length) return { action: 'start' };
  return {
    action: generatingDocs.every(doc => doc.inputHash === inputHash)
      ? 'same_generation' : 'newer_input',
    generatingDocs,
  };
}


async function launchReportGeneration(input) {
  const campaignId = String(input.campaignId || '').trim();
  if (!campaignId) throw new Error('campaignId required');
  const snapshot = await require('./reportDatasets').activeSnapshot(campaignId);
  if (snapshot) {
    // Scenario facts and prose are a pinned revision. A normal report retry
    // must not silently regenerate a different, invisible legacy projection.
    return { status: 'already_ready', campaignId, reportVersion: 2,
      inputHash: snapshot.inputHash, revision: snapshot.revision, scenarioManaged: true };
  }
  const zones = (input.zones || []).map(zone => (
    typeof zone === 'string' ? inferReportZone(zone) : zone
  ));
  const normalized = normalizeReportInput({
    ...input,
    campaignId,
    zones: zones.length ? zones : [inferReportZone('znews_homepage_banner')],
  });
  // This flag is deliberately outside the normalized contract and input hash:
  // it authorizes an explicit legacy migration, not a different campaign.
  normalized.allowLegacyUpgrade = input.allowLegacyUpgrade === true;

  const docs = await ReportAnalysis.find(
    { campaignId },
    { status: 1, schemaVersion: 1, dataContract: 1, inputHash: 1, pendingInput: 1, updatedAt: 1 }
  ).lean();
  const inspection = inspectReportGeneration(
    docs, normalized.inputHash, normalized.allowLegacyUpgrade
  );
  // A normal visit to an old campaign must remain read-only. Conversion is an
  // intentional operator action, never a side effect of opening/retrying it.
  if (inspection.action === 'preserve_legacy') {
    return { status: 'already_ready', campaignId, reportVersion: 1, preservedLegacy: true };
  }
  if (inspection.action === 'already_ready') {
    return { status: 'already_ready', campaignId, reportVersion: 2, inputHash: normalized.inputHash };
  }

  const generatingDocs = inspection.generatingDocs || [];
  if (generatingDocs.length) {
    if (hasActiveReportGeneration(generatingDocs)) {
      if (inspection.action === 'same_generation') {
        return { status: 'already_generating', campaignId, inputHash: normalized.inputHash };
      }

      await ReportAnalysis.updateMany(
        { campaignId, status: 'generating' },
        { $set: { pendingInput: normalized } }
      );
      return { status: 'queued', campaignId, inputHash: normalized.inputHash, reportVersion: 2 };
    }
    console.warn(`[reports/generate] Reclaiming stale generation lease for ${campaignId}`);
  }

  await Promise.all(REPORT_TYPES.map(reportType => ReportAnalysis.findOneAndUpdate(
    { campaignId, reportType },
    { $set: {
      status: 'generating', error: '', inputHash: normalized.inputHash,
      schemaVersion: EVIDENCE_V2, pendingInput: null,
    } },
    { upsert: true }
  )));

  setImmediate(async () => {
    try {
      await generateReports(normalized);
    } catch (err) {
      console.error('[reports/generate] Background generation failed:', err.message);
    }
  });
  return {
    status: 'generating', campaignId, inputHash: normalized.inputHash,
    reportVersion: 2,
  };
}


module.exports = { inferReportZone, inspectReportGeneration, launchReportGeneration };
