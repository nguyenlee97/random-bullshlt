const ReportAnalysis = require('../models/ReportAnalysis');
const { generateReports, getReportStatus, REPORT_TYPES } = require('./reportGenerator');
const { hasActiveReportGeneration } = require('../lib/reportGenerationLease');
const { normalizeReportInput } = require('../lib/reportMeasurement');


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


async function launchReportGeneration(input) {
  const campaignId = String(input.campaignId || '').trim();
  if (!campaignId) throw new Error('campaignId required');
  const zones = (input.zones || []).map(zone => (
    typeof zone === 'string' ? inferReportZone(zone) : zone
  ));
  const normalized = normalizeReportInput({
    ...input,
    campaignId,
    zones: zones.length ? zones : [inferReportZone('znews_homepage_banner')],
  });

  const current = await getReportStatus(campaignId);
  const readyForInput = await ReportAnalysis.countDocuments({
    campaignId, status: 'ready', schemaVersion: 'report-evidence-v2',
    inputHash: normalized.inputHash,
  });
  if (current.ready >= current.total && current.contractReady >= current.total
      && readyForInput >= current.total) {
    return { status: 'already_ready', campaignId };
  }
  if (Object.values(current.types || {}).includes('generating')) {
    const generatingDocs = await ReportAnalysis.find(
      { campaignId, status: 'generating' },
      { status: 1, updatedAt: 1 }
    ).lean();
    if (hasActiveReportGeneration(generatingDocs)) {
      return { status: 'already_generating', campaignId };
    }
    console.warn(`[reports/generate] Reclaiming stale generation lease for ${campaignId}`);
  }

  await Promise.all(REPORT_TYPES.map(reportType => ReportAnalysis.findOneAndUpdate(
    { campaignId, reportType },
    { $set: { status: 'generating', error: '' } },
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


module.exports = { inferReportZone, launchReportGeneration };
