const ReportAnalysis = require('../models/ReportAnalysis');
const { generateReports, getReportStatus, REPORT_TYPES } = require('./reportGenerator');
const { hasActiveReportGeneration } = require('../lib/reportGenerationLease');


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

  const current = await getReportStatus(campaignId);
  if (current.ready >= current.total) {
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

  const zones = (input.zones || []).map(zone => (
    typeof zone === 'string' ? inferReportZone(zone) : zone
  ));
  setImmediate(async () => {
    try {
      await generateReports({
        campaignId,
        brand: input.brand || 'Unknown Brand',
        objective: input.objective || 'awareness',
        budget: input.budget || 100000000,
        startDate: input.startDate || new Date().toISOString().slice(0, 10),
        zones: zones.length ? zones : [inferReportZone('znews_homepage_banner')],
        audience: input.audience || [],
      });
    } catch (err) {
      console.error('[reports/generate] Background generation failed:', err.message);
    }
  });
  return { status: 'generating', campaignId };
}


module.exports = { inferReportZone, launchReportGeneration };
