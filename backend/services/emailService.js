/**
 * emailService.js — Send campaign report emails via Resend
 */
const { Resend } = require('resend');

const resend = new Resend(process.env.RESEND_API_KEY);
const FROM = process.env.RESEND_FROM || 'onboarding@resend.dev';

// ── Formatters ────────────────────────────────────────────────────────────────
function fmtN(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K';
  return String(Math.round(n));
}
function fmtVND(n) {
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B ₫';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M ₫';
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K ₫';
  return n + ' ₫';
}

// ── HTML email builder ────────────────────────────────────────────────────────
function buildHtmlBody({ brand, objective, campaignId, totals, overallText }) {
  const { impressions = 0, clicks = 0, spend = 0, conversions = 0, reach = 0 } = totals;
  const ctr = impressions > 0 ? (clicks / impressions * 100).toFixed(2) : '0.00';
  const date = new Date().toLocaleString('vi-VN');

  const kpiTop = [
    { label: 'Impressions', value: fmtN(impressions), color: '#3b82f6', bg: '#eff6ff' },
    { label: 'Clicks',      value: fmtN(clicks),      color: '#f59e0b', bg: '#fffbeb' },
    { label: 'CTR',         value: ctr + '%',          color: '#10b981', bg: '#ecfdf5' },
  ];
  const kpiBot = [
    { label: 'Total Spend',  value: fmtVND(spend),       color: '#8b5cf6', bg: '#f5f3ff' },
    { label: 'Reach',        value: fmtN(reach),          color: '#ec4899', bg: '#fdf2f8' },
    { label: 'Conversions',  value: fmtN(conversions),    color: '#06b6d4', bg: '#ecfeff' },
  ];

  const tile = (k) => `
    <td width="33%" style="padding:0 8px 12px 0;">
      <div style="background:${k.bg};border-radius:10px;padding:14px;text-align:center;">
        <p style="margin:0;font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;">${k.label}</p>
        <p style="margin:6px 0 0;font-size:22px;font-weight:800;color:${k.color};">${k.value}</p>
      </div>
    </td>`;

  return `<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f8f9fc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fc;padding:32px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

  <!-- HEADER -->
  <tr><td style="background:linear-gradient(135deg,#0068ff,#0057d9);padding:36px 40px;">
    <table width="100%"><tr>
      <td>
        <p style="margin:0;color:rgba(255,255,255,.76);font-size:11px;text-transform:uppercase;letter-spacing:2px;">Advertising Agent</p>
        <h1 style="margin:8px 0 0;color:#fff;font-size:26px;font-weight:800;">Báo cáo chiến dịch</h1>
        <p style="margin:6px 0 0;color:rgba(255,255,255,.9);font-size:16px;font-weight:600;">${brand}</p>
      </td>
      <td align="right" valign="top">
        <div style="background:rgba(255,255,255,.15);border-radius:10px;padding:12px 16px;text-align:center;">
          <p style="margin:0;color:rgba(255,255,255,.7);font-size:10px;text-transform:uppercase;">Objective</p>
          <p style="margin:4px 0 0;color:#fff;font-size:14px;font-weight:700;text-transform:capitalize;">${objective}</p>
        </div>
      </td>
    </tr></table>
  </td></tr>

  <!-- CAMPAIGN ID -->
  <tr><td style="background:#eaf3ff;padding:10px 40px;border-bottom:1px solid #d8e9ff;">
    <p style="margin:0;font-size:11px;color:#6b7280;">
      Campaign ID: <strong style="color:#0068ff;">${campaignId}</strong>
      &nbsp;·&nbsp; Tạo lúc: <strong>${date}</strong>
    </p>
  </td></tr>

  <!-- KPI TILES -->
  <tr><td style="padding:28px 40px 8px;">
    <p style="margin:0 0 16px;font-size:12px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.5px;">📊 Tổng quan KPI</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>${kpiTop.map(tile).join('')}</tr>
      <tr>${kpiBot.map(tile).join('')}</tr>
    </table>
  </td></tr>

  <!-- AI SUMMARY -->
  ${overallText ? `
  <tr><td style="padding:4px 40px 24px;">
    <div style="background:#f7faff;border-left:4px solid #0068ff;border-radius:0 10px 10px 0;padding:16px 20px;">
      <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#0068ff;text-transform:uppercase;">🤖 AI Executive Summary</p>
      <p style="margin:0;font-size:13px;color:#374151;line-height:1.7;">${overallText}</p>
    </div>
  </td></tr>` : ''}

  <!-- ATTACHMENT NOTICE -->
  <tr><td style="padding:0 40px 28px;">
    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:14px 18px;">
      <p style="margin:0;font-size:13px;color:#15803d;">
        📎 <strong>File đính kèm:</strong> Báo cáo PDF đầy đủ với phân tích 6 hạng mục —
        Daily Ops, Awareness, Consideration, Conversion, Retention, Executive.
      </p>
    </div>
  </td></tr>

  <!-- FOOTER -->
  <tr><td style="background:#f9fafb;border-top:1px solid #f3f4f6;padding:20px 40px;text-align:center;">
    <p style="margin:0;font-size:11px;color:#9ca3af;">Được tạo bởi <strong>Advertising Agent</strong></p>
    <p style="margin:4px 0 0;font-size:11px;color:#d1d5db;">Email này được gửi tự động. Vui lòng không reply.</p>
  </td></tr>

</table>
</td></tr>
</table>
</body></html>`;
}

// ── CSV converter ─────────────────────────────────────────────────────────────
function recordsToCsv(records) {
  if (!records.length) return 'No data';
  const cols = ['campaignId','placementId','channel','format','date',
    'impressions','clicks','reach','spend','conversions','vi','ctr','cpm'];
  const rows = records.map(r =>
    cols.map(h => {
      const v = r[h] ?? '';
      return typeof v === 'string' && v.includes(',') ? `"${v}"` : v;
    }).join(',')
  );
  return [cols.join(','), ...rows].join('\n');
}

// ── Main export ───────────────────────────────────────────────────────────────
/**
 * Send campaign report email via Resend.
 * @param {Object} opts
 * @param {string}  opts.to           recipient email
 * @param {string}  [opts.cc]         CC email
 * @param {string}  opts.campaignId
 * @param {string}  opts.brand
 * @param {string}  opts.objective
 * @param {Object}  opts.totals       { impressions, clicks, spend, conversions, reach }
 * @param {string}  opts.overallText  executive AI summary
 * @param {Buffer}  opts.pdfBuffer    PDF attachment buffer
 * @param {boolean} opts.attachCsv
 * @param {boolean} opts.attachJson
 * @param {Array}   opts.records      raw analytics records
 */
async function sendCampaignReport(opts) {
  const {
    to, cc, campaignId, brand, objective,
    totals = {}, overallText = '',
    pdfBuffer, attachCsv = false, attachJson = false, records = [],
  } = opts;

  const subject = `[Advertising Agent] Báo cáo chiến dịch ${brand} — ${new Date().toLocaleDateString('vi-VN')}`;
  const html = buildHtmlBody({ brand, objective, campaignId, totals, overallText });

  const attachments = [];
  if (pdfBuffer) {
    attachments.push({ filename: `report_${campaignId}.pdf`, content: pdfBuffer.toString('base64') });
  }
  if (attachCsv && records.length) {
    attachments.push({ filename: `analytics_${campaignId}.csv`, content: Buffer.from(recordsToCsv(records)).toString('base64') });
  }
  if (attachJson && records.length) {
    attachments.push({ filename: `analytics_${campaignId}.json`, content: Buffer.from(JSON.stringify(records, null, 2)).toString('base64') });
  }

  const payload = { from: FROM, to: [to], subject, html, attachments };
  if (cc) payload.cc = [cc];

  console.log(`[emailService] Sending to=${to} attachments=${attachments.map(a => a.filename).join(', ')}`);
  const { data, error } = await resend.emails.send(payload);
  if (error) throw new Error(`Resend error: ${JSON.stringify(error)}`);

  console.log(`[emailService] Sent OK — id=${data?.id}`);
  return { ok: true, messageId: data?.id };
}

module.exports = { sendCampaignReport };
