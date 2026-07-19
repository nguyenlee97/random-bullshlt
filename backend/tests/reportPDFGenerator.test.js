const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildPDF,
  validatePackage,
  REPORT_ORDER,
  _internals,
} = require('../services/reportPDFGenerator');

function records() {
  const placements = ['ZingNews_Masthead', 'BaoMoi_Masthead', 'ZingMP3_Masthead'];
  return Array.from({ length: 14 }, (_, day) => placements.map((placementId, index) => ({
    campaignId: 'ORD-PDF-1', placementId,
    date: `2026-07-${String(day + 1).padStart(2, '0')}`,
    impressions: 100000 + day * 1200 - index * 5000,
    clicks: 700 + day * 6 - index * 20,
    spend: 650000 + day * 3000 - index * 20000,
    reach: 70000 + day * 500 - index * 2500,
    conversions: 25 + day - index,
    vi: 0.9 - index * 0.08,
  }))).flat();
}

function analyses() {
  return REPORT_ORDER.map(reportType => ({
    reportType,
    status: 'ready',
    overall: 'Chiến dịch phân phối ổn định, độ phủ tốt và cần tiếp tục theo dõi hiệu quả theo từng vị trí.',
    questions: Array.from({ length: 6 }, (_, index) => ({
      id: `${reportType}_${index}`,
      question: `Câu hỏi phân tích ${index + 1} cho báo cáo ${reportType}?`,
      answer: { sections: [
        { type: 'summary', text: 'Số liệu cho thấy hiệu suất ổn định trong giai đoạn được phân tích.' },
        { type: 'metrics', items: [
          { label: 'Tổng impressions', value: '4.270.000', trend: 'stable', delta: '0%' },
          { label: 'Tổng clicks', value: '27.876', trend: 'up', delta: '2%' },
        ] },
        { type: 'insight', level: 'warning', text: 'Một số placement cần được theo dõi thêm về CTR và viewability.' },
        { type: 'recommendation', items: [
          { priority: 'high', text: 'Ưu tiên các placement đang có chất lượng phân phối tốt.' },
        ] },
      ] },
    })),
  }));
}

test('complete PDF embeds a Unicode font and renders six chart/Q&A report sections', async () => {
  assert.ok(_internals.resolveFontPath('regular'));
  assert.ok(_internals.resolveFontPath('bold'));
  const buffer = await buildPDF({
    campaignId: 'ORD-PDF-1',
    campaign: { orderId: 'ORD-PDF-1', brand: 'Thương hiệu Việt', objective: 'awareness' },
    records: records(), analyses: analyses(), compress: false,
  });
  const source = buffer.toString('latin1');
  assert.equal(buffer.subarray(0, 4).toString('ascii'), '%PDF');
  assert.ok(buffer.length > 100000, `expected embedded-font PDF, received ${buffer.length} bytes`);
  const pageCount = (source.match(/\/Type \/Page\b/g) || []).length;
  assert.ok(pageCount >= 15, `expected a complete multi-section report, received ${pageCount} pages`);
  assert.ok(pageCount <= 35, `unexpected pagination overflow produced ${pageCount} pages`);
  assert.doesNotMatch(source, /\bNaN\b/);
  assert.doesNotMatch(source, /Helvetica/);
});

test('PDF stays unavailable until records and all six analyses are ready', () => {
  assert.throws(
    () => validatePackage(records(), analyses().slice(0, 5)),
    error => error.code === 'REPORT_NOT_READY' && error.missingTypes.length === 1,
  );
  assert.throws(
    () => validatePackage([], analyses()),
    error => error.code === 'REPORT_NOT_READY',
  );
});
