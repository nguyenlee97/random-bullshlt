const DEFAULT_REPORT_GENERATION_LEASE_MS = 15 * 60 * 1000;

function reportGenerationLeaseMs(env = process.env) {
  const configured = Number(env.REPORT_GENERATION_LEASE_MS);
  return Number.isFinite(configured) && configured > 0
    ? configured
    : DEFAULT_REPORT_GENERATION_LEASE_MS;
}

function hasActiveReportGeneration(docs, options = {}) {
  const nowMs = options.nowMs ?? Date.now();
  const leaseMs = options.leaseMs ?? reportGenerationLeaseMs();

  return docs.some((doc) => {
    if (doc.status !== 'generating' || !doc.updatedAt) return false;
    const updatedAtMs = new Date(doc.updatedAt).getTime();
    return Number.isFinite(updatedAtMs)
      && updatedAtMs <= nowMs
      && nowMs - updatedAtMs < leaseMs;
  });
}

module.exports = {
  DEFAULT_REPORT_GENERATION_LEASE_MS,
  reportGenerationLeaseMs,
  hasActiveReportGeneration,
};
