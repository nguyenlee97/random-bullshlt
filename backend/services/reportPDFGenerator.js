/**
 * reportPDFGenerator.js — Generate a campaign report PDF using PDFKit
 * Pure JS, no headless browser required.
 * Sections: Cover → Executive → KPI Scorecard → per-tab analysis → Zone Table
 */
const PDFDocument = require('pdfkit');
const ReportAnalysis = require('../models/ReportAnalysis');
const AnalyticsRecord = require('../models/AnalyticsRecord');

// ── Colors / theme ─────────────────────────────────────────────────────────────
const C = {
  primary:   '#0068ff',
  secondary: '#0057d9',
  accent:    '#38a3ff',
  warn:      '#f59e0b',
  danger:    '#ef4444',
  text:      '#111827',
  muted:     '#6b7280',
  light:     '#f3f4f6',
  white:     '#ffffff',
  border:    '#e5e7eb',
};

// ── Number formatters ──────────────────────────────────────────────────────────
function fmtN(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(0) + 'K';
  return String(Math.round(n));
}
function fmtVND(n) {
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B ₫';
  if (n >= 1_000_000)     return (n / 1_000_000).toFixed(1) + 'M ₫';
  if (n >= 1_000)         return (n / 1_000).toFixed(0) + 'K ₫';
  return n + ' ₫';
}
function fmtPct(n) { return (n * 100).toFixed(2) + '%'; }

// ── Drawing helpers ─────────────────────────────────────────────────────────────
function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return [r, g, b];
}

function fillRect(doc, x, y, w, h, color) {
  const [r, g, b] = hexToRgb(color);
  doc.save().rect(x, y, w, h).fill([r, g, b]).restore();
}

function textColor(doc, color) {
  const [r, g, b] = hexToRgb(color);
  doc.fillColor([r, g, b]);
}

// ── Section header ──────────────────────────────────────────────────────────────
function sectionHeader(doc, title, color = C.primary) {
  const y = doc.y;
  fillRect(doc, 40, y, 515, 28, color);
  textColor(doc, C.white);
  doc.fontSize(11).font('Helvetica-Bold').text(title, 50, y + 8, { width: 500 });
  doc.moveDown(0.3);
}

// ── KPI tile row ────────────────────────────────────────────────────────────────
function kpiRow(doc, items) {
  const colW = 515 / items.length;
  const y = doc.y;
  const h = 52;
  items.forEach((item, i) => {
    const x = 40 + i * colW;
    fillRect(doc, x + 2, y, colW - 4, h, C.light);
    textColor(doc, C.muted);
    doc.fontSize(8).font('Helvetica').text(item.label.toUpperCase(), x + 6, y + 7, { width: colW - 12, align: 'center' });
    textColor(doc, C.text);
    doc.fontSize(14).font('Helvetica-Bold').text(item.value, x + 6, y + 21, { width: colW - 12, align: 'center' });
  });
  doc.y = y + h + 6;
}

// ── Horizontal bar chart ────────────────────────────────────────────────────────
function horizontalBars(doc, items, maxVal, color = C.primary) {
  const barH = 14, gap = 6, labelW = 130, barMaxW = 260;
  items.forEach(item => {
    const y = doc.y;
    const pct = maxVal > 0 ? item.value / maxVal : 0;
    const barW = Math.max(2, Math.round(pct * barMaxW));
    // label
    textColor(doc, C.text);
    doc.fontSize(8).font('Helvetica').text(String(item.label).slice(0, 22), 40, y + 3, { width: labelW - 4 });
    // bar background
    fillRect(doc, 40 + labelW, y, barMaxW, barH, C.light);
    // bar fill
    fillRect(doc, 40 + labelW, y, barW, barH, color);
    // value
    textColor(doc, C.muted);
    doc.fontSize(8).font('Helvetica').text(item.display || fmtN(item.value), 40 + labelW + barMaxW + 4, y + 3);
    doc.y = y + barH + gap;
  });
  doc.moveDown(0.5);
}

// ── Simple line "chart" as ASCII-style sparkline using dots ───────────────────
function sparklineText(doc, values, label) {
  if (!values.length) return;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const levels = 4;
  const bars = values.map(v => {
    const lvl = Math.round((v - min) / range * (levels - 1));
    return ['▁','▃','▅','▇'][lvl];
  });
  textColor(doc, C.muted);
  doc.fontSize(8).font('Helvetica').text(`${label}: ${bars.join('')}  min=${fmtN(min)}  max=${fmtN(max)}`, 40, doc.y);
  doc.moveDown(0.4);
}

// ── Zone performance table ──────────────────────────────────────────────────────
function zoneTable(doc, records) {
  // Aggregate by placementId
  const map = {};
  records.forEach(r => {
    const id = r.placementId || 'unknown';
    if (!map[id]) map[id] = { id, imp: 0, clk: 0, spend: 0, conv: 0, n: 0 };
    map[id].imp   += r.impressions  || 0;
    map[id].clk   += r.clicks       || 0;
    map[id].spend += r.spend        || 0;
    map[id].conv  += r.conversions  || 0;
    map[id].n++;
  });
  const zones = Object.values(map).sort((a, b) => b.imp - a.imp).slice(0, 15);

  const cols = [
    { label: 'Zone',        w: 140 },
    { label: 'Imps',        w:  60 },
    { label: 'Clicks',      w:  50 },
    { label: 'CTR',         w:  50 },
    { label: 'Spend',       w:  80 },
    { label: 'Conv',        w:  45 },
    { label: 'CPM',         w:  70 },
  ];
  const totalW = cols.reduce((s, c) => s + c.w, 0);
  const startX = 40;

  // Header row
  let x = startX, y = doc.y;
  fillRect(doc, startX, y, totalW, 18, C.primary);
  textColor(doc, C.white);
  doc.fontSize(8).font('Helvetica-Bold');
  cols.forEach(col => {
    doc.text(col.label, x + 3, y + 5, { width: col.w - 6 });
    x += col.w;
  });
  y += 18;

  // Data rows
  zones.forEach((z, idx) => {
    x = startX;
    if (idx % 2 === 0) fillRect(doc, startX, y, totalW, 16, '#f9fafb');
    textColor(doc, C.text);
    doc.fontSize(7.5).font('Helvetica');
    const ctr = z.imp > 0 ? (z.clk / z.imp * 100).toFixed(2) + '%' : '0%';
    const cpm = z.imp > 0 ? fmtVND(Math.round(z.spend / z.imp * 1000)) : '—';
    const row = [z.id.replace(/_/g, ' ').slice(0, 22), fmtN(z.imp), fmtN(z.clk), ctr, fmtVND(z.spend), String(z.conv), cpm];
    row.forEach((val, ci) => {
      doc.text(val, x + 3, y + 4, { width: cols[ci].w - 6 });
      x += cols[ci].w;
    });
    y += 16;
    if (y > 730) { doc.addPage(); y = 60; }
  });
  doc.y = y + 8;
}

// ── Analysis section (one report type) ─────────────────────────────────────────
function renderAnalysisSection(doc, analysis, records) {
  if (!analysis) return;

  const typeLabels = {
    daily_ops:     '📊 Daily Ops',
    awareness:     '👁 Awareness',
    consideration: '🖱 Consideration',
    conversion:    '🎯 Conversion',
    retention:     '🔄 Retention',
    executive:     '💼 Executive',
  };
  const typeColors = {
    daily_ops:     '#3b82f6',
    awareness:     '#8b5cf6',
    consideration: '#f59e0b',
    conversion:    '#10b981',
    retention:     '#ec4899',
    executive:     '#6366f1',
  };

  const label = typeLabels[analysis.reportType] || analysis.reportType;
  const color = typeColors[analysis.reportType] || C.primary;

  if (doc.y > 650) doc.addPage();

  sectionHeader(doc, label, color);

  // Overall summary
  if (analysis.overall) {
    textColor(doc, C.text);
    doc.fontSize(9).font('Helvetica').text(analysis.overall, 40, doc.y, {
      width: 515, align: 'justify', lineGap: 2,
    });
    doc.moveDown(0.6);
  }

  // Q&A pairs — top 3 questions
  const questions = (analysis.questions || []).slice(0, 3);
  questions.forEach((q, qi) => {
    if (doc.y > 680) { doc.addPage(); }
    textColor(doc, C.primary);
    doc.fontSize(8.5).font('Helvetica-Bold').text(`Q${qi + 1}: ${q.question}`, 40, doc.y, { width: 515 });
    doc.moveDown(0.15);

    const answer = q.answer || {};
    const sections = answer.sections || [];
    sections.forEach(s => {
      if (s.type === 'summary' && s.text) {
        textColor(doc, C.text);
        doc.fontSize(8).font('Helvetica').text(s.text, 50, doc.y, { width: 505, lineGap: 1.5 });
        doc.moveDown(0.3);
      }
      if (s.type === 'insights' && Array.isArray(s.items)) {
        s.items.slice(0, 3).forEach(item => {
          textColor(doc, C.muted);
          doc.fontSize(8).font('Helvetica').text('• ' + item, 55, doc.y, { width: 500, lineGap: 1.5 });
          doc.moveDown(0.2);
        });
      }
      if (s.type === 'table' && Array.isArray(s.rows)) {
        s.rows.slice(0, 5).forEach(row => {
          const line = Array.isArray(row) ? row.join('  |  ') : String(row);
          textColor(doc, C.text);
          doc.fontSize(7.5).font('Helvetica').text('  ' + line, 55, doc.y, { width: 500 });
          doc.moveDown(0.2);
        });
      }
    });
    doc.moveDown(0.4);
  });

  // Mini sparklines from records for this section
  if (records.length && ['daily_ops','awareness','consideration','conversion'].includes(analysis.reportType)) {
    const byDate = {};
    records.forEach(r => {
      if (!byDate[r.date]) byDate[r.date] = { imp: 0, clk: 0 };
      byDate[r.date].imp += r.impressions || 0;
      byDate[r.date].clk += r.clicks || 0;
    });
    const dates = Object.keys(byDate).sort();
    if (dates.length > 1) {
      sparklineText(doc, dates.map(d => byDate[d].imp), 'Impressions trend');
      sparklineText(doc, dates.map(d => byDate[d].clk), 'Clicks trend');
    }
  }

  doc.moveDown(0.5);
}

// ── Main generate function ──────────────────────────────────────────────────────
async function generatePDF(campaignId) {
  // Fetch data from MongoDB
  const [records, analyses] = await Promise.all([
    AnalyticsRecord.find({ campaignId }).lean(),
    ReportAnalysis.find({ campaignId, status: 'ready' }).lean(),
  ]);

  // Compute totals
  const totals = records.reduce((acc, r) => {
    acc.impressions  += r.impressions  || 0;
    acc.clicks       += r.clicks       || 0;
    acc.spend        += r.spend        || 0;
    acc.conversions  += r.conversions  || 0;
    acc.reach        += r.reach        || 0;
    return acc;
  }, { impressions: 0, clicks: 0, spend: 0, conversions: 0, reach: 0 });

  const ctr = totals.impressions > 0 ? totals.clicks / totals.impressions : 0;
  const cpm = totals.impressions > 0 ? Math.round(totals.spend / totals.impressions * 1000) : 0;

  // Find executive analysis for brand/objective
  const execAnalysis = analyses.find(a => a.reportType === 'executive') || {};
  const brand     = execAnalysis.brand || campaignId;
  const objective = execAnalysis.objective || 'awareness';

  // ── Build PDF ──────────────────────────────────────────────────────────────
  const doc = new PDFDocument({
    size: 'A4',
    margins: { top: 40, bottom: 40, left: 40, right: 40 },
    info: {
      Title: `Campaign Report — ${brand}`,
      Author: 'Advertising Agent',
      Subject: `Performance Report for ${campaignId}`,
    },
  });

  const chunks = [];
  doc.on('data', chunk => chunks.push(chunk));

  // ── PAGE 1: COVER ──────────────────────────────────────────────────────────
  // Full-page gradient header
  fillRect(doc, 0, 0, 595, 220, C.primary);

  textColor(doc, C.white);
  doc.fontSize(10).font('Helvetica').text('ADVERTISING AGENT', 40, 60, { characterSpacing: 3 });
  doc.fontSize(28).font('Helvetica-Bold').text('Campaign Report', 40, 80);
  doc.fontSize(18).font('Helvetica').text(brand, 40, 118);

  // Meta box
  fillRect(doc, 40, 150, 240, 50, 'rgba(255,255,255,0)');
  fillRect(doc, 40, 150, 240, 50, '#004dbd');
  textColor(doc, C.white);
  doc.fontSize(9).font('Helvetica').text(`Objective: ${objective.toUpperCase()}`, 50, 161);
  doc.fontSize(9).text(`Campaign ID: ${campaignId}`, 50, 176);

  doc.y = 240;

  // Cover KPI tiles
  textColor(doc, C.text);
  doc.fontSize(12).font('Helvetica-Bold').text('Campaign Performance Overview', 40, doc.y);
  doc.moveDown(0.5);

  kpiRow(doc, [
    { label: 'Total Impressions', value: fmtN(totals.impressions) },
    { label: 'Total Clicks',      value: fmtN(totals.clicks) },
    { label: 'Overall CTR',       value: fmtPct(ctr) },
  ]);
  kpiRow(doc, [
    { label: 'Total Spend',   value: fmtVND(totals.spend) },
    { label: 'Total Reach',   value: fmtN(totals.reach) },
    { label: 'Avg CPM',       value: fmtVND(cpm) },
  ]);

  doc.moveDown(1);
  textColor(doc, C.muted);
  doc.fontSize(9).font('Helvetica')
    .text(`Generated by Advertising Agent on ${new Date().toLocaleString('vi-VN')}`, 40, doc.y, { align: 'center', width: 515 });

  // ── PAGE 2: PER-TAB ANALYSIS ───────────────────────────────────────────────
  const ORDER = ['daily_ops', 'awareness', 'consideration', 'conversion', 'retention', 'executive'];
  for (const rtype of ORDER) {
    const analysis = analyses.find(a => a.reportType === rtype);
    if (!analysis) continue;
    doc.addPage();
    renderAnalysisSection(doc, analysis, records);
  }

  // ── LAST PAGE: ZONE PERFORMANCE TABLE ─────────────────────────────────────
  if (records.length > 0) {
    doc.addPage();
    sectionHeader(doc, '📋 Zone Performance — Full Breakdown', C.text);
    doc.moveDown(0.3);
    zoneTable(doc, records);
  }

  doc.end();

  return new Promise((resolve, reject) => {
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);
  });
}

module.exports = { generatePDF };
