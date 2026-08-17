/**
 * Generate a complete Unicode campaign report with PDFKit.
 *
 * The PDF intentionally uses vector charts and embedded fonts instead of HTML
 * screenshots, so the same export works for browser download, email, and Zalo.
 */
const fs = require('fs');
const path = require('path');
const PDFDocument = require('pdfkit');
const Campaign = require('../models/Campaign');
const ReportAnalysis = require('../models/ReportAnalysis');
const AnalyticsRecord = require('../models/AnalyticsRecord');

const C = {
  primary:   '#0068ff',
  secondary: '#0057d9',
  accent:    '#38a3ff',
  warn:      '#f59e0b',
  danger:    '#ef4444',
  success:   '#10b981',
  pink:      '#ec4899',
  purple:    '#8b5cf6',
  text:      '#111827',
  muted:     '#64748b',
  light:     '#f3f6fa',
  white:     '#ffffff',
  border:    '#dbe3ee',
};

// Reserve the final 65 points for a footer. PDFKit may create a new page when
// text is positioned inside the document bottom margin, even with lineBreak
// disabled, so all flowing content must remain above this boundary.
const PAGE = { width: 595.28, height: 841.89, left: 40, right: 555, bottom: 775 };
const FONT = { regular: 'ReportRegular', bold: 'ReportBold' };
const REPORT_ORDER = ['daily_ops', 'awareness', 'consideration', 'conversion', 'retention', 'executive'];
const REPORT_META = {
  daily_ops:     { label: 'Daily Ops', color: '#3b82f6' },
  awareness:     { label: 'Awareness', color: '#8b5cf6' },
  consideration: { label: 'Consideration', color: '#f59e0b' },
  conversion:    { label: 'Conversion', color: '#10b981' },
  retention:     { label: 'Retention', color: '#ec4899' },
  executive:     { label: 'Executive', color: '#6366f1' },
};

function safeNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function cleanText(value) {
  return String(value ?? '')
    .normalize('NFC')
    .replace(/[\u2010-\u2015\u2212]/g, '-')
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '')
    .trim();
}

function fmtN(value) {
  const number = safeNumber(value);
  if (Math.abs(number) >= 1_000_000_000) return `${(number / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(number) >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}M`;
  if (Math.abs(number) >= 1_000) return `${(number / 1_000).toFixed(1)}K`;
  return Math.round(number).toLocaleString('en-US');
}

function fmtVND(value) {
  return `${fmtN(value)} VND`;
}

function fmtPct(value, digits = 2) {
  return `${safeNumber(value).toFixed(digits)}%`;
}

function resolveFontPath(kind) {
  const isBold = kind === 'bold';
  const environmentPath = isBold ? process.env.REPORT_PDF_FONT_BOLD : process.env.REPORT_PDF_FONT_REGULAR;
  const candidates = [
    environmentPath,
    path.join(__dirname, '..', 'assets', 'fonts', isBold ? 'DejaVuSans-Bold.ttf' : 'DejaVuSans.ttf'),
    isBold ? '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' : '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    isBold ? '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf' : '/usr/share/fonts/dejavu/DejaVuSans.ttf',
    isBold ? 'C:\\Windows\\Fonts\\arialbd.ttf' : 'C:\\Windows\\Fonts\\arial.ttf',
  ].filter(Boolean);
  const selected = candidates.find(candidate => fs.existsSync(candidate));
  if (!selected) {
    throw new Error(`Unicode PDF font unavailable (${kind}). Set REPORT_PDF_FONT_${isBold ? 'BOLD' : 'REGULAR'}.`);
  }
  return selected;
}

function registerFonts(doc) {
  doc.registerFont(FONT.regular, resolveFontPath('regular'));
  doc.registerFont(FONT.bold, resolveFontPath('bold'));
}

function fillRect(doc, x, y, width, height, color, radius = 0) {
  const values = [x, y, width, height].map(safeNumber);
  if (values[2] <= 0 || values[3] <= 0) return;
  doc.save();
  if (radius > 0) doc.roundedRect(...values, radius);
  else doc.rect(...values);
  doc.fill(color);
  doc.restore();
}

function strokeLine(doc, x1, y1, x2, y2, color = C.border, width = 1) {
  doc.save().lineWidth(width).strokeColor(color)
    .moveTo(safeNumber(x1), safeNumber(y1)).lineTo(safeNumber(x2), safeNumber(y2)).stroke().restore();
}

function fitText(doc, value, width, maxHeight, options = {}) {
  const font = options.font || FONT.regular;
  const size = options.size || 9;
  const lineGap = options.lineGap ?? 1.5;
  let text = cleanText(value);
  doc.font(font).fontSize(size);
  if (doc.heightOfString(text, { width, lineGap }) <= maxHeight) return text;
  let low = 0;
  let high = text.length;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    const candidate = `${text.slice(0, middle).trim()}...`;
    if (doc.heightOfString(candidate, { width, lineGap }) <= maxHeight) low = middle;
    else high = middle - 1;
  }
  return `${text.slice(0, low).trim()}...`;
}

function totalsFor(records) {
  const totals = records.reduce((acc, row) => {
    for (const key of ['impressions', 'clicks', 'spend', 'reach', 'conversions']) {
      acc[key] += safeNumber(row[key]);
    }
    if (row.vi !== null && row.vi !== undefined) {
      acc.viSum += safeNumber(row.vi);
      acc.viCount += 1;
    }
    return acc;
  }, { impressions: 0, clicks: 0, spend: 0, reach: 0, conversions: 0, viSum: 0, viCount: 0 });
  totals.ctr = totals.impressions ? totals.clicks / totals.impressions * 100 : 0;
  totals.cpm = totals.impressions ? totals.spend / totals.impressions * 1000 : 0;
  totals.cvr = totals.clicks ? totals.conversions / totals.clicks * 100 : 0;
  totals.cpa = totals.conversions ? totals.spend / totals.conversions : 0;
  totals.frequency = totals.reach ? totals.impressions / totals.reach : 0;
  totals.viewability = totals.viCount ? totals.viSum / totals.viCount : 0;
  return totals;
}

function aggregateRows(records, groupKey) {
  const grouped = new Map();
  for (const record of records) {
    const rawKey = typeof groupKey === 'function' ? groupKey(record) : record[groupKey];
    const key = cleanText(rawKey || 'Unknown');
    if (!grouped.has(key)) grouped.set(key, { key, rows: [] });
    grouped.get(key).rows.push(record);
  }
  return [...grouped.values()].map(group => ({
    ...group,
    ...totalsFor(group.rows),
  }));
}

function dailyRows(records) {
  return aggregateRows(records, row => String(row.date || '').slice(0, 10))
    .sort((a, b) => a.key.localeCompare(b.key));
}

function zoneRows(records) {
  return aggregateRows(records, row => row.placementId || row.placement || 'Unknown')
    .sort((a, b) => b.impressions - a.impressions);
}

function reportMetrics(reportType, totals) {
  const universal = {
    impressions: ['Impressions', fmtN(totals.impressions)],
    clicks: ['Clicks', fmtN(totals.clicks)],
    ctr: ['CTR', fmtPct(totals.ctr)],
    spend: ['Spend', fmtVND(totals.spend)],
    reach: ['Reach', fmtN(totals.reach)],
    viewability: ['Viewability', fmtPct(totals.viewability)],
    cpm: ['CPM', fmtVND(totals.cpm)],
    conversions: ['Conversions', fmtN(totals.conversions)],
    cvr: ['CVR', fmtPct(totals.cvr)],
    cpa: ['CPA', fmtVND(totals.cpa)],
    frequency: ['Frequency', `${totals.frequency.toFixed(2)}x`],
  };
  const keys = {
    daily_ops: ['impressions', 'clicks', 'ctr', 'spend', 'conversions', 'cpm'],
    awareness: ['reach', 'impressions', 'frequency', 'cpm', 'viewability', 'spend'],
    consideration: ['clicks', 'ctr', 'impressions', 'cpm', 'viewability', 'spend'],
    conversion: ['conversions', 'cvr', 'cpa', 'clicks', 'spend', 'impressions'],
    retention: ['reach', 'frequency', 'ctr', 'viewability', 'impressions', 'clicks'],
    executive: ['spend', 'reach', 'impressions', 'ctr', 'conversions', 'cpm'],
  }[reportType] || ['impressions', 'clicks', 'ctr', 'spend', 'reach', 'viewability'];
  return keys.map(key => ({ label: universal[key][0], value: universal[key][1] }));
}

function metricValueLabel(key, value) {
  if (['ctr', 'cvr', 'viewability'].includes(key)) return fmtPct(value);
  if (key === 'frequency') return `${safeNumber(value).toFixed(2)}x`;
  if (['spend', 'cpm', 'cpa'].includes(key)) return fmtVND(value);
  return fmtN(value);
}

function chartConfiguration(reportType) {
  return {
    daily_ops: {
      first: ['Daily delivery - Impressions and Clicks', ['impressions', 'clicks']],
      second: ['Spend and CTR trend', ['spend', 'ctr']],
      placement: ['Impressions by placement', 'impressions'],
    },
    awareness: {
      first: ['Daily Reach and Impressions', ['reach', 'impressions']],
      second: ['CPM and Viewability trend', ['cpm', 'viewability']],
      placement: ['Viewability by placement', 'viewability'],
    },
    consideration: {
      first: ['Clicks and CTR trend', ['clicks', 'ctr']],
      second: ['CPM and Viewability trend', ['cpm', 'viewability']],
      placement: ['CTR by placement', 'ctr'],
    },
    conversion: {
      first: ['Conversions and CVR trend', ['conversions', 'cvr']],
      second: ['CPA and Spend trend', ['cpa', 'spend']],
      placement: ['Conversions by placement', 'conversions'],
    },
    retention: {
      first: ['Reach and Frequency trend', ['reach', 'frequency']],
      second: ['CTR and Viewability trend', ['ctr', 'viewability']],
      placement: ['Frequency by placement', 'frequency'],
    },
    executive: {
      first: ['Spend and Impressions trend', ['spend', 'impressions']],
      second: ['CTR and Conversions trend', ['ctr', 'conversions']],
      placement: ['Spend by placement', 'spend'],
    },
  }[reportType];
}

function pageHeader(doc, title, subtitle, color = C.primary) {
  const cleanTitle = cleanText(title);
  const titleSize = cleanTitle.length > 50 ? 14 : cleanTitle.length > 39 ? 16 : 19;
  fillRect(doc, 0, 0, PAGE.width, 78, color);
  doc.fillColor(C.white).font(FONT.bold).fontSize(titleSize)
    .text(cleanTitle, 40, 24, { width: 515, lineBreak: false });
  if (subtitle) {
    doc.font(FONT.regular).fontSize(8.5)
      .text(cleanText(subtitle), 40, 51, { width: 515, lineBreak: false });
  }
  doc.y = 96;
}

function drawMetricCards(doc, items, y) {
  const gap = 8;
  const cardWidth = (515 - gap * 2) / 3;
  for (let index = 0; index < items.length; index += 1) {
    const row = Math.floor(index / 3);
    const column = index % 3;
    const x = 40 + column * (cardWidth + gap);
    const cardY = y + row * 58;
    fillRect(doc, x, cardY, cardWidth, 50, C.light, 7);
    doc.fillColor(C.muted).font(FONT.bold).fontSize(7.2)
      .text(cleanText(items[index].label).toUpperCase(), x + 9, cardY + 8, { width: cardWidth - 18 });
    doc.fillColor(C.text).font(FONT.bold).fontSize(14)
      .text(cleanText(items[index].value), x + 9, cardY + 23, { width: cardWidth - 18 });
  }
}

function panel(doc, x, y, width, height, title) {
  doc.save().roundedRect(x, y, width, height, 7).fillAndStroke(C.white, C.border).restore();
  doc.fillColor(C.text).font(FONT.bold).fontSize(9.5)
    .text(cleanText(title), x + 12, y + 10, { width: width - 24 });
}

function drawLineChart(doc, { x, y, width, height, title, rows, keys, colors }) {
  panel(doc, x, y, width, height, title);
  const plot = { x: x + 36, y: y + 34, width: width - 50, height: height - 64 };
  for (let grid = 0; grid <= 3; grid += 1) {
    const gridY = plot.y + plot.height * grid / 3;
    strokeLine(doc, plot.x, gridY, plot.x + plot.width, gridY, '#e8edf4', 0.6);
  }
  keys.forEach((key, seriesIndex) => {
    const values = rows.map(row => safeNumber(row[key]));
    const maximum = Math.max(...values, 1);
    const points = values.map((value, index) => ({
      x: plot.x + plot.width * index / Math.max(1, values.length - 1),
      y: plot.y + plot.height - plot.height * value / maximum,
    }));
    if (points.length > 1) {
      doc.save().lineWidth(1.8).strokeColor(colors[seriesIndex]).moveTo(points[0].x, points[0].y);
      points.slice(1).forEach(point => doc.lineTo(point.x, point.y));
      doc.stroke().restore();
    }
    points.forEach(point => fillRect(doc, point.x - 1.8, point.y - 1.8, 3.6, 3.6, colors[seriesIndex], 1.8));
  });
  if (rows.length) {
    doc.fillColor(C.muted).font(FONT.regular).fontSize(6.5)
      .text(cleanText(rows[0].key).slice(5), plot.x, plot.y + plot.height + 5, { width: 45 });
    doc.text(cleanText(rows[rows.length - 1].key).slice(5), plot.x + plot.width - 45, plot.y + plot.height + 5, { width: 45, align: 'right' });
  }
  let legendX = x + 12;
  keys.forEach((key, index) => {
    fillRect(doc, legendX, y + height - 15, 8, 8, colors[index], 2);
    const average = rows.length ? rows.reduce((sum, row) => sum + safeNumber(row[key]), 0) / rows.length : 0;
    const label = `${key.toUpperCase()} avg ${metricValueLabel(key, average)}`;
    doc.fillColor(C.muted).font(FONT.regular).fontSize(6.5).text(label, legendX + 12, y + height - 15, { width: 125 });
    legendX += 150;
  });
}

function drawPlacementBars(doc, { x, y, width, height, title, rows, key, color }) {
  panel(doc, x, y, width, height, title);
  const selected = rows.slice(0, 6);
  const maximum = Math.max(...selected.map(row => safeNumber(row[key])), 1);
  const labelWidth = 128;
  const valueWidth = 70;
  const barWidth = width - labelWidth - valueWidth - 32;
  selected.forEach((row, index) => {
    const rowY = y + 36 + index * 21;
    const value = safeNumber(row[key]);
    doc.fillColor(C.text).font(FONT.regular).fontSize(7)
      .text(cleanText(row.key).replace(/_/g, ' ').slice(0, 28), x + 12, rowY + 2, { width: labelWidth - 6 });
    fillRect(doc, x + labelWidth, rowY, barWidth, 10, C.light, 5);
    fillRect(doc, x + labelWidth, rowY, Math.max(2, barWidth * value / maximum), 10, color, 5);
    doc.fillColor(C.muted).font(FONT.regular).fontSize(7)
      .text(metricValueLabel(key, value), x + labelWidth + barWidth + 6, rowY + 1, { width: valueWidth - 6, align: 'right' });
  });
}

function renderReportAnalytics(doc, reportType, analysis, records, campaign) {
  const meta = REPORT_META[reportType];
  const totals = totalsFor(records);
  const daily = dailyRows(records);
  const zones = zoneRows(records);
  const charts = chartConfiguration(reportType);
  doc.addPage();
  pageHeader(doc, `${meta.label} Report`, `${campaign.brand} | ${campaign.orderId}`, meta.color);

  fillRect(doc, 40, 95, 515, 70, '#f7f9fc', 7);
  doc.fillColor(meta.color).font(FONT.bold).fontSize(8).text('OVERALL ANALYSIS', 52, 106);
  const overall = fitText(doc, analysis?.overall || 'No overall analysis is available.', 491, 41, { size: 8.2, lineGap: 1.3 });
  doc.fillColor(C.text).font(FONT.regular).fontSize(8.2).text(overall, 52, 123, { width: 491, lineGap: 1.3 });

  drawMetricCards(doc, reportMetrics(reportType, totals), 177);
  drawLineChart(doc, {
    x: 40, y: 302, width: 515, height: 150, title: charts.first[0], rows: daily,
    keys: charts.first[1], colors: [meta.color, C.accent],
  });
  drawLineChart(doc, {
    x: 40, y: 464, width: 515, height: 150, title: charts.second[0], rows: daily,
    keys: charts.second[1], colors: [C.warn, C.success],
  });
  drawPlacementBars(doc, {
    x: 40, y: 626, width: 515, height: 149, title: charts.placement[0], rows: zones,
    key: charts.placement[1], color: meta.color,
  });
}

function qaPage(doc, reportType, campaign, continuation = false) {
  const meta = REPORT_META[reportType];
  doc.addPage();
  pageHeader(
    doc,
    `${meta.label} - Generated Q&A${continuation ? ' (continued)' : ''}`,
    `Full report analysis | ${campaign.brand} | ${campaign.orderId}`,
    meta.color,
  );
}

function ensureQASpace(doc, required, reportType, campaign) {
  if (doc.y + required <= PAGE.bottom) return;
  qaPage(doc, reportType, campaign, true);
}

function paragraph(doc, text, reportType, campaign, options = {}) {
  const width = options.width || 491;
  const x = options.x || 52;
  const font = options.bold ? FONT.bold : FONT.regular;
  const size = options.size || 8.2;
  const lineGap = options.lineGap ?? 1.4;
  const value = cleanText(text);
  if (!value) return;
  doc.font(font).fontSize(size);
  const height = doc.heightOfString(value, { width, lineGap }) + 4;
  ensureQASpace(doc, Math.min(height, 680), reportType, campaign);
  doc.fillColor(options.color || C.text).font(font).fontSize(size)
    .text(value, x, doc.y, { width, lineGap });
  doc.y += options.after ?? 4;
}

function renderAnswerSection(doc, section, reportType, campaign) {
  if (!section || typeof section !== 'object') return;
  if (section.type === 'summary' && section.text) {
    paragraph(doc, section.text, reportType, campaign);
    return;
  }
  if (section.type === 'metrics' && Array.isArray(section.items)) {
    for (let index = 0; index < section.items.length; index += 2) {
      const pair = section.items.slice(index, index + 2);
      const cardWidth = 235;
      const textWidth = cardWidth - 14;
      const cardHeight = Math.max(34, ...pair.map(item => {
        const suffix = item.delta ? ` (${cleanText(item.delta)})` : '';
        doc.font(FONT.bold).fontSize(7.2);
        return 23 + doc.heightOfString(`${cleanText(item.value)}${suffix}`, {
          width: textWidth,
          lineGap: 1,
        });
      }));
      ensureQASpace(doc, cardHeight + 5, reportType, campaign);
      const rowY = doc.y;
      pair.forEach((item, pairIndex) => {
        const x = 52 + pairIndex * 247;
        fillRect(doc, x, rowY, cardWidth, cardHeight, C.light, 5);
        doc.fillColor(C.muted).font(FONT.regular).fontSize(6.8)
          .text(cleanText(item.label), x + 7, rowY + 5, { width: textWidth, lineBreak: false });
        const suffix = item.delta ? ` (${cleanText(item.delta)})` : '';
        doc.fillColor(C.text).font(FONT.bold).fontSize(7.2)
          .text(`${cleanText(item.value)}${suffix}`, x + 7, rowY + 16, {
            width: textWidth,
            lineGap: 1,
          });
      });
      doc.y = rowY + cardHeight + 5;
    }
    return;
  }
  if (section.type === 'insights' && Array.isArray(section.items)) {
    section.items.forEach(item => paragraph(doc, `- ${cleanText(item)}`, reportType, campaign, { x: 58, width: 485 }));
    return;
  }
  if (section.type === 'insight' && section.text) {
    ensureQASpace(doc, 30, reportType, campaign);
    fillRect(doc, 52, doc.y, 491, 3, section.level === 'warning' ? C.warn : C.accent);
    doc.y += 8;
    paragraph(doc, section.text, reportType, campaign, { x: 58, width: 479, color: C.text });
    return;
  }
  if (section.type === 'recommendation' && Array.isArray(section.items)) {
    paragraph(doc, 'Recommendations', reportType, campaign, { bold: true, color: C.success, after: 2 });
    section.items.forEach(item => {
      const priority = item && typeof item === 'object' ? cleanText(item.priority || '') : '';
      const text = item && typeof item === 'object' ? cleanText(item.text || '') : cleanText(item);
      paragraph(doc, `- ${priority ? `[${priority.toUpperCase()}] ` : ''}${text}`, reportType, campaign, { x: 58, width: 485 });
    });
    return;
  }
  if (section.type === 'table' && Array.isArray(section.rows)) {
    section.rows.forEach(row => {
      const values = Array.isArray(row) ? row : Object.values(row || {});
      paragraph(doc, values.map(cleanText).join(' | '), reportType, campaign, { x: 58, width: 485, size: 7.2 });
    });
  }
}

function renderReportQA(doc, reportType, analysis, campaign) {
  qaPage(doc, reportType, campaign);
  const questions = analysis?.questions || [];
  if (!questions.length) {
    paragraph(doc, 'No generated questions are available for this report.', reportType, campaign);
    return;
  }
  questions.forEach((question, index) => {
    ensureQASpace(doc, 70, reportType, campaign);
    paragraph(doc, `Q${index + 1}. ${cleanText(question.question)}`, reportType, campaign, {
      bold: true, size: 9.2, color: REPORT_META[reportType].color, after: 4,
    });
    const sections = question.answer?.sections || [];
    if (!sections.length) {
      paragraph(doc, 'No generated answer is available.', reportType, campaign, { color: C.muted });
    } else {
      sections.forEach(section => renderAnswerSection(doc, section, reportType, campaign));
    }
    doc.y += 7;
    if (doc.y < PAGE.bottom) strokeLine(doc, 52, doc.y, 543, doc.y, C.border, 0.6);
    doc.y += 9;
  });
}

function drawTableHeader(doc, columns, y, color = C.primary) {
  fillRect(doc, PAGE.left, y, 515, 20, color);
  let x = PAGE.left;
  doc.fillColor(C.white).font(FONT.bold).fontSize(6.8);
  columns.forEach(column => {
    doc.text(column.label, x + 4, y + 6, { width: column.width - 8 });
    x += column.width;
  });
}

function drawTableRow(doc, columns, values, y, index) {
  if (index % 2 === 0) fillRect(doc, PAGE.left, y, 515, 19, '#f7f9fc');
  let x = PAGE.left;
  doc.fillColor(C.text).font(FONT.regular).fontSize(6.5);
  values.forEach((value, columnIndex) => {
    doc.text(cleanText(value), x + 4, y + 6, { width: columns[columnIndex].width - 8 });
    x += columns[columnIndex].width;
  });
}

function renderZoneAppendix(doc, records, campaign) {
  const columns = [
    { label: 'Zone', width: 145 }, { label: 'Imps', width: 55 },
    { label: 'Clicks', width: 45 }, { label: 'CTR', width: 45 },
    { label: 'Spend', width: 70 }, { label: 'Conv', width: 40 },
    { label: 'VI%', width: 45 }, { label: 'CPM', width: 70 },
  ];
  const rows = zoneRows(records);
  doc.addPage();
  pageHeader(doc, 'Appendix A - Zone Performance', `${campaign.brand} | ${campaign.orderId}`, C.text);
  let y = 105;
  drawTableHeader(doc, columns, y);
  y += 20;
  rows.forEach((row, index) => {
    if (y > 775) {
      doc.addPage();
      pageHeader(doc, 'Appendix A - Zone Performance (continued)', `${campaign.brand} | ${campaign.orderId}`, C.text);
      y = 105;
      drawTableHeader(doc, columns, y);
      y += 20;
    }
    drawTableRow(doc, columns, [
      row.key.replace(/_/g, ' '), fmtN(row.impressions), fmtN(row.clicks), fmtPct(row.ctr),
      fmtVND(row.spend), fmtN(row.conversions), fmtPct(row.viewability), fmtVND(row.cpm),
    ], y, index);
    y += 19;
  });
}

function renderDailyAppendix(doc, records, campaign) {
  const columns = [
    { label: 'Date', width: 75 }, { label: 'Imps', width: 70 },
    { label: 'Clicks', width: 55 }, { label: 'CTR', width: 55 },
    { label: 'Spend', width: 80 }, { label: 'Reach', width: 70 },
    { label: 'Conv', width: 50 }, { label: 'CPM', width: 60 },
  ];
  const rows = dailyRows(records);
  doc.addPage();
  pageHeader(doc, 'Appendix B - Daily Performance', `${campaign.brand} | ${campaign.orderId}`, C.text);
  let y = 105;
  drawTableHeader(doc, columns, y);
  y += 20;
  rows.forEach((row, index) => {
    if (y > 775) {
      doc.addPage();
      pageHeader(doc, 'Appendix B - Daily Performance (continued)', `${campaign.brand} | ${campaign.orderId}`, C.text);
      y = 105;
      drawTableHeader(doc, columns, y);
      y += 20;
    }
    drawTableRow(doc, columns, [
      row.key, fmtN(row.impressions), fmtN(row.clicks), fmtPct(row.ctr), fmtVND(row.spend),
      fmtN(row.reach), fmtN(row.conversions), fmtVND(row.cpm),
    ], y, index);
    y += 19;
  });
}

function coverPage(doc, campaign, records, analyses) {
  const totals = totalsFor(records);
  fillRect(doc, 0, 0, PAGE.width, 235, C.primary);
  doc.fillColor(C.white).font(FONT.regular).fontSize(9)
    .text('ADVERTISING AGENT', 40, 58, { characterSpacing: 2.5 });
  doc.font(FONT.bold).fontSize(28).text('Campaign Report', 40, 82, { width: 515 });
  doc.font(FONT.regular).fontSize(17).text(cleanText(campaign.brand), 40, 125, { width: 515 });
  fillRect(doc, 40, 163, 280, 48, C.secondary, 7);
  doc.fontSize(8.5).text(`Objective: ${cleanText(campaign.objective).toUpperCase()}`, 52, 176);
  doc.text(`Campaign ID: ${cleanText(campaign.orderId)}`, 52, 191);

  doc.fillColor(C.text).font(FONT.bold).fontSize(13).text('Campaign Performance Overview', 40, 264);
  drawMetricCards(doc, reportMetrics('executive', totals), 290);

  doc.fillColor(C.text).font(FONT.bold).fontSize(12).text('Report contents', 40, 424);
  REPORT_ORDER.forEach((type, index) => {
    const analysis = analyses.find(item => item.reportType === type);
    const y = 454 + index * 34;
    fillRect(doc, 40, y, 515, 27, index % 2 ? '#f7f9fc' : C.light, 5);
    fillRect(doc, 51, y + 7, 12, 12, REPORT_META[type].color, 3);
    doc.fillColor(C.text).font(FONT.bold).fontSize(8.5)
      .text(`${index + 1}. ${REPORT_META[type].label}`, 72, y + 8, { width: 190 });
    doc.fillColor(analysis ? C.success : C.danger).font(FONT.regular).fontSize(7.5)
      .text(analysis ? `${analysis.questions?.length || 0} generated Q&A` : 'Not ready', 360, y + 9, { width: 170, align: 'right' });
  });
  const generatedAt = new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh',
  }).format(new Date());
  doc.fillColor(C.muted).font(FONT.regular).fontSize(8)
    .text(`Generated by Advertising Agent on ${cleanText(generatedAt)}`, 40, 700, { width: 515, align: 'center' });
}

function addFooters(doc) {
  const range = doc.bufferedPageRange();
  for (let index = range.start; index < range.start + range.count; index += 1) {
    doc.switchToPage(index);
    // Draw inside the reserved footer band without PDFKit applying the normal
    // content bottom margin. Otherwise pages whose content cursor is low can
    // clip this text down to a single character.
    const bottomMargin = doc.page.margins.bottom;
    doc.page.margins.bottom = 0;
    strokeLine(doc, 40, 804, 555, 804, C.border, 0.5);
    doc.fillColor(C.muted).font(FONT.regular).fontSize(6.8)
      .text(`Page ${index + 1} of ${range.count}`, 430, 811, {
      width: 125, height: 12, align: 'right',
    });
    doc.page.margins.bottom = bottomMargin;
  }
  const finalRange = doc.bufferedPageRange();
  if (finalRange.count !== range.count) {
    throw new Error('PDF footer overflow created unexpected pages');
  }
}

function validatePackage(records, analyses) {
  if (!records.length) {
    const error = new Error('Report data is not ready');
    error.code = 'REPORT_NOT_READY';
    throw error;
  }
  const readyTypes = new Set(analyses.map(item => item.reportType));
  const missing = REPORT_ORDER.filter(type => !readyTypes.has(type));
  if (missing.length) {
    const error = new Error(`Report is still generating: ${missing.join(', ')}`);
    error.code = 'REPORT_NOT_READY';
    error.missingTypes = missing;
    throw error;
  }
}

function buildPDF({ campaignId, campaign = {}, records = [], analyses = [], compress = true }) {
  validatePackage(records, analyses);
  const campaignMeta = {
    orderId: campaign.orderId || campaignId,
    brand: campaign.brand || campaignId,
    objective: campaign.objective || 'awareness',
  };
  const doc = new PDFDocument({
    size: 'A4', margin: 40, bufferPages: true, compress,
    info: {
      Title: `Campaign Report - ${cleanText(campaignMeta.brand)}`,
      Author: 'Advertising Agent',
      Subject: `Complete performance report for ${cleanText(campaignMeta.orderId)}`,
    },
  });
  registerFonts(doc);
  const chunks = [];
  doc.on('data', chunk => chunks.push(chunk));
  coverPage(doc, campaignMeta, records, analyses);
  REPORT_ORDER.forEach(reportType => {
    const analysis = analyses.find(item => item.reportType === reportType);
    renderReportAnalytics(doc, reportType, analysis, records, campaignMeta);
    renderReportQA(doc, reportType, analysis, campaignMeta);
  });
  renderZoneAppendix(doc, records, campaignMeta);
  renderDailyAppendix(doc, records, campaignMeta);
  addFooters(doc);
  doc.end();
  return new Promise((resolve, reject) => {
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);
  });
}

async function generatePDF(campaignId) {
  const [campaign, records, analyses] = await Promise.all([
    Campaign.findOne({ orderId: campaignId }).lean(),
    AnalyticsRecord.find({ campaignId }).sort({ date: 1 }).lean(),
    ReportAnalysis.find({ campaignId, status: 'ready' }).lean(),
  ]);
  return buildPDF({ campaignId, campaign: campaign || {}, records, analyses });
}

module.exports = {
  generatePDF,
  buildPDF,
  validatePackage,
  REPORT_ORDER,
  _internals: { cleanText, dailyRows, zoneRows, totalsFor, resolveFontPath },
};
