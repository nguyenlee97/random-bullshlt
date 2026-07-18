/**
 * reportGenerator.js — OpenAI-powered synthetic analytics data generator
 *
 * Generates 14-day synthetic performance data for each ad zone in a campaign,
 * then generates pre-built analysis Q&A for each of the 6 report types.
 *
 * Output:
 *   - analytics_records: 14 records × N zones (same 13-field schema)
 *   - report_analyses: 6 documents with pre-generated Q&A
 */
const AnalyticsRecord = require('../models/AnalyticsRecord');
const ReportAnalysis = require('../models/ReportAnalysis');

const OPENAI_API_KEY = process.env.OPENAI_API_KEY || '';
const OPENAI_MODEL = process.env.OPENAI_MODEL || 'gpt-5.4-mini';
const OPENAI_URL = 'https://api.openai.com/v1/chat/completions';

// ─── Report types ────────────────────────────────────────────────────────────
const REPORT_TYPES = [
  'daily_ops', 'awareness', 'consideration', 'conversion', 'retention', 'executive',
];

// ─── Predefined questions per report type ────────────────────────────────────
const QUESTIONS_MAP = {
  daily_ops: [
    { id: 'op_q1', question: 'Tổng quan hiệu suất chiến dịch', category: 'performance' },
    { id: 'op_q2', question: 'So sánh hiệu suất giữa các ad zone', category: 'comparison' },
    { id: 'op_q3', question: 'Phân tích xu hướng CTR theo thời gian', category: 'trend' },
    { id: 'op_q4', question: 'Đánh giá hiệu quả chi tiêu', category: 'performance' },
    { id: 'op_q5', question: 'Top zone có hiệu suất tốt nhất', category: 'comparison' },
    { id: 'op_q6', question: 'Gợi ý tối ưu chiến dịch', category: 'optimization' },
  ],
  awareness: [
    { id: 'aw_q1', question: 'Phân tích Reach & Frequency', category: 'performance' },
    { id: 'aw_q2', question: 'Đánh giá Viewability theo zone', category: 'comparison' },
    { id: 'aw_q3', question: 'So sánh hiệu quả CPM giữa các zone', category: 'comparison' },
    { id: 'aw_q4', question: 'Phân tích Video completion rate', category: 'performance' },
    { id: 'aw_q5', question: 'Đánh giá mức độ phủ sóng thương hiệu', category: 'performance' },
    { id: 'aw_q6', question: 'Gợi ý tối ưu nhận diện thương hiệu', category: 'optimization' },
  ],
  consideration: [
    { id: 'co_q1', question: 'Phân tích CTR theo zone', category: 'performance' },
    { id: 'co_q2', question: 'So sánh CTR vs CPM', category: 'comparison' },
    { id: 'co_q3', question: 'Phân tích click volume trend', category: 'trend' },
    { id: 'co_q4', question: 'CTR theo ad format (banner vs skin)', category: 'comparison' },
    { id: 'co_q5', question: 'Top zone engagement', category: 'comparison' },
    { id: 'co_q6', question: 'Gợi ý tăng cường tương tác', category: 'optimization' },
  ],
  conversion: [
    { id: 'cv_q1', question: 'Phân tích tỷ lệ chuyển đổi theo channel', category: 'performance' },
    { id: 'cv_q2', question: 'Đánh giá CPA theo placement', category: 'comparison' },
    { id: 'cv_q3', question: 'So sánh Spend vs Conversions', category: 'comparison' },
    { id: 'cv_q4', question: 'Conversion funnel analysis', category: 'performance' },
    { id: 'cv_q5', question: 'Top converting zones', category: 'comparison' },
    { id: 'cv_q6', question: 'Gợi ý tối ưu chuyển đổi', category: 'optimization' },
  ],
  retention: [
    { id: 'rt_q1', question: 'Đánh giá tần suất tiếp cận theo zone', category: 'performance' },
    { id: 'rt_q2', question: 'CTR decay & creative fatigue analysis', category: 'trend' },
    { id: 'rt_q3', question: 'Week-over-week reach analysis', category: 'trend' },
    { id: 'rt_q4', question: 'Audience saturation analysis', category: 'performance' },
    { id: 'rt_q5', question: 'Gợi ý chống bão hòa quảng cáo', category: 'optimization' },
    { id: 'rt_q6', question: 'Chiến lược retention & re-engagement', category: 'optimization' },
  ],
  executive: [
    { id: 'ex_q1', question: 'Tổng quan sức khỏe chiến dịch', category: 'performance' },
    { id: 'ex_q2', question: 'Phân tích pacing ngân sách', category: 'performance' },
    { id: 'ex_q3', question: 'So sánh KPI kỳ đầu vs kỳ sau', category: 'comparison' },
    { id: 'ex_q4', question: 'Phân bổ ngân sách theo channel', category: 'comparison' },
    { id: 'ex_q5', question: 'Smart recommendations', category: 'optimization' },
    { id: 'ex_q6', question: 'Tổng hợp & đề xuất chiến lược', category: 'optimization' },
  ],
};

// ─── OpenAI call helper ──────────────────────────────────────────────────────
function buildOpenAIRequestBody(model, messages, temperature, maxCompletionTokens) {
  const body = {
    model,
    messages,
    max_completion_tokens: maxCompletionTokens,
    response_format: { type: 'json_object' },
  };
  // GPT-5-family chat models reject non-default sampling parameters. Older
  // compatible models may still use the configured report temperature.
  if (!String(model).toLowerCase().startsWith('gpt-5')) {
    body.temperature = temperature;
  }
  return body;
}


async function callOpenAI(messages, { temperature = 0.7, max_completion_tokens = 8000 } = {}) {
  if (!OPENAI_API_KEY) throw new Error('OPENAI_API_KEY not set');
  console.log(`[openai] → model=${OPENAI_MODEL} max_completion_tokens=${max_completion_tokens} prompt_len=${JSON.stringify(messages).length}`);
  const res = await fetch(OPENAI_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${OPENAI_API_KEY}`,
    },
    body: JSON.stringify(buildOpenAIRequestBody(
      OPENAI_MODEL, messages, temperature, max_completion_tokens,
    )),
  });
  const raw = await res.text();
  if (!res.ok) {
    console.error(`[openai] ✗ HTTP ${res.status}: ${raw.slice(0, 500)}`);
    throw new Error(`OpenAI ${res.status}: ${raw.slice(0, 300)}`);
  }
  let data;
  try {
    data = JSON.parse(raw);
  } catch (e) {
    console.error(`[openai] ✗ JSON parse failed: ${raw.slice(0, 300)}`);
    throw new Error(`OpenAI response not valid JSON: ${raw.slice(0, 200)}`);
  }
  const usage = data.usage || {};
  const content = data.choices?.[0]?.message?.content || '{}';
  console.log(`[openai] ✓ tokens: prompt=${usage.prompt_tokens} completion=${usage.completion_tokens} total=${usage.total_tokens} | content_len=${content.length}`);
  console.log(`[openai] content_preview: ${content.slice(0, 200)}`);
  let parsed;
  try {
    parsed = JSON.parse(content);
  } catch (e) {
    console.error(`[openai] ✗ content JSON parse failed: ${content.slice(0, 300)}`);
    throw new Error(`OpenAI content not valid JSON: ${content.slice(0, 200)}`);
  }
  return parsed;
}

// ─── Generate synthetic analytics records ────────────────────────────────────
async function generateRecords(campaign) {
  const { campaignId, brand, objective, budget, startDate, zones } = campaign;

  // Calculate date range: 14 days from startDate
  const start = new Date(startDate);
  const dates = [];
  for (let i = 0; i < 14; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    dates.push(d.toISOString().slice(0, 10));
  }

  const zoneList = zones.map(z => `${z.id} (channel: ${z.channel}, format: ${z.format}, baseCPM: ${z.cpm})`).join('\n');

  const prompt = `Generate realistic synthetic ad campaign performance data.

CAMPAIGN:
- Brand: ${brand}
- Objective: ${objective}
- Budget: ${budget} VND total (${Math.round(budget / 1000000)}M VND)
- Duration: 14 days from ${dates[0]} to ${dates[13]}
- Zones:\n${zoneList}

RULES:
1. Generate exactly ${zones.length * 14} records (14 days × ${zones.length} zones)
2. Each record must have these exact fields: campaignId, placementId, date, channel, format, impressions, clicks, spend, ctr, cpm, reach, conversions, vi
3. campaignId is always "${campaignId}"
4. ctr = clicks/impressions*100 (rounded to 3 decimals)
5. cpm ≈ spend/impressions*1000
6. reach should be 65-85% of impressions
7. vi (viewability) should be 50-95% depending on format (banner higher, skin lower)
8. Total spend across all records should be approximately ${Math.round(budget * 0.85)} VND (85% of budget)
9. For ${objective} campaigns: ${objective === 'awareness' ? 'prioritize high impressions, high vi (70-95%), moderate ctr (0.3-0.8%)' : objective === 'conversion' ? 'moderate impressions, higher ctr (0.6-1.5%), more conversions (2-5% of clicks)' : objective === 'consideration' ? 'balanced impressions, good ctr (0.5-1.2%), moderate conversions' : 'moderate everything with emphasis on reach and frequency'}
10. Include realistic patterns: weekdays slightly higher than weekends, gradual ramp-up in first 3 days, possible mid-campaign dip around day 7-8
11. Vary metrics between zones — some zones should perform better than others
12. conversions: for awareness campaigns use 0.3-1% of clicks, for conversion campaigns use 2-5% of clicks

OUTPUT FORMAT: Return JSON with key "records" containing the array.
{ "records": [ { "campaignId": "...", "placementId": "...", "date": "YYYY-MM-DD", "channel": "...", "format": "...", "impressions": N, "clicks": N, "spend": N, "ctr": N, "cpm": N, "reach": N, "conversions": N, "vi": N }, ... ] }`;

  const result = await callOpenAI([
    { role: 'system', content: 'You are a data generator. Output ONLY valid JSON. Generate realistic advertising performance data.' },
    { role: 'user', content: prompt },
  ], { temperature: 0.8, max_completion_tokens: 16000 });

  return result.records || [];
}

// ─── Generate analysis for one report type ───────────────────────────────────
async function generateAnalysis(campaign, records, reportType) {
  const questions = QUESTIONS_MAP[reportType] || [];
  const questionList = questions.map(q => `- ${q.id}: "${q.question}" (${q.category})`).join('\n');

  // Summarize records for context
  const totalImp = records.reduce((s, r) => s + (r.impressions || 0), 0);
  const totalClk = records.reduce((s, r) => s + (r.clicks || 0), 0);
  const totalSpend = records.reduce((s, r) => s + (r.spend || 0), 0);
  const totalConv = records.reduce((s, r) => s + (r.conversions || 0), 0);
  const avgCTR = totalImp > 0 ? (totalClk / totalImp * 100).toFixed(3) : 0;
  const avgVI = records.length > 0 ? (records.reduce((s, r) => s + (r.vi || 0), 0) / records.length).toFixed(1) : 0;

  // Per-zone summary
  const zoneMap = {};
  records.forEach(r => {
    if (!zoneMap[r.placementId]) zoneMap[r.placementId] = { imp: 0, clk: 0, spend: 0, conv: 0, vi: 0, n: 0 };
    const z = zoneMap[r.placementId];
    z.imp += r.impressions || 0;
    z.clk += r.clicks || 0;
    z.spend += r.spend || 0;
    z.conv += r.conversions || 0;
    z.vi += r.vi || 0;
    z.n++;
  });
  const zoneSummary = Object.entries(zoneMap).map(([id, z]) =>
    `${id}: ${z.imp} imps, ${z.clk} clicks, CTR ${z.imp > 0 ? (z.clk / z.imp * 100).toFixed(2) : 0}%, Spend ${Math.round(z.spend / 1000000)}M, VI ${(z.vi / z.n).toFixed(1)}%`
  ).join('\n');

  const prompt = `You are an expert digital advertising analyst. Analyze this campaign data and answer predefined questions.

CAMPAIGN: ${campaign.brand} | Objective: ${campaign.objective} | Budget: ${Math.round(campaign.budget / 1000000)}M VND
PERIOD: 14 days | Zones: ${Object.keys(zoneMap).length}

TOTALS: ${totalImp.toLocaleString()} impressions | ${totalClk.toLocaleString()} clicks | CTR ${avgCTR}% | Spend ${Math.round(totalSpend / 1000000)}M VND | ${totalConv} conversions | Avg VI ${avgVI}%

PER-ZONE:
${zoneSummary}

REPORT TYPE: ${reportType.replace('_', ' ').toUpperCase()}

QUESTIONS TO ANSWER:
${questionList}

For each question, provide a structured analysis. Output JSON:
{
  "overall": "2-3 sentence overall summary for this report type in Vietnamese",
  "questions": [
    {
      "id": "question_id",
      "answer": {
        "sections": [
          { "type": "summary", "text": "1-2 sentence summary in Vietnamese" },
          { "type": "metrics", "items": [
            { "label": "Metric Name", "value": "formatted value", "trend": "up|down|stable", "delta": "+X%" }
          ]},
          { "type": "insight", "level": "good|warning|bad", "text": "Key insight in Vietnamese" },
          { "type": "recommendation", "items": [
            { "priority": "high|medium|low", "text": "Action recommendation in Vietnamese" }
          ]}
        ]
      }
    }
  ]
}

RULES:
- All text in Vietnamese
- Use specific numbers from the data
- Be professional and actionable
- Each answer should have 2-4 sections
- Include at least one recommendation per answer`;

  const result = await callOpenAI([
    { role: 'system', content: 'You are a Vietnamese digital advertising analyst. Output ONLY valid JSON. Be specific, data-driven, and professional.' },
    { role: 'user', content: prompt },
  ], { temperature: 0.6, max_completion_tokens: 8000 });

  return result;
}

// ─── Main: generate all reports for a campaign ───────────────────────────────
async function generateReports(campaign) {
  const { campaignId } = campaign;
  console.log(`[reportGen] Starting generation for campaign ${campaignId}`);

  // Check if records already exist AND have real data
  const existing = await AnalyticsRecord.countDocuments({ campaignId });
  const existingWithData = existing > 0
    ? await AnalyticsRecord.countDocuments({ campaignId, impressions: { $gt: 0 } })
    : 0;

  if (existing > 0 && existingWithData === 0) {
    console.log(`[reportGen] ⚠️  ${existing} records found but ALL ZEROS — deleting and regenerating`);
    await AnalyticsRecord.deleteMany({ campaignId });
  }

  const shouldGenerate = existing === 0 || existingWithData === 0;
  if (!shouldGenerate) {
    console.log(`[reportGen] ${existing} records (${existingWithData} with data) already exist for ${campaignId} — reusing`);
  }

  // Step 1: Generate synthetic records (if not already present with real data)
  let records;
  if (shouldGenerate) {
    try {
      records = await generateRecords(campaign);
      console.log(`[reportGen] OpenAI returned ${records.length} records`);
      if (records.length > 0) {
        await AnalyticsRecord.insertMany(records);
        console.log(`[reportGen] Inserted ${records.length} analytics records for ${campaignId}`);
      } else {
        console.error(`[reportGen] ⚠️  OpenAI returned 0 records — check prompt or API response`);
      }
    } catch (err) {
      console.error(`[reportGen] Record generation failed:`, err.message);
      // Mark all report types as error
      for (const rt of REPORT_TYPES) {
        await ReportAnalysis.findOneAndUpdate(
          { campaignId, reportType: rt },
          { $set: { status: 'error', error: err.message } },
          { upsert: true }
        );
      }
      throw err;
    }
  } else {
    records = await AnalyticsRecord.find({ campaignId }).lean();
    console.log(`[reportGen] Loaded ${records.length} existing records for ${campaignId}`);
  }

  // Step 2: Generate analyses for each report type (parallel)
  const analysisPromises = REPORT_TYPES.map(async (reportType) => {
    // Create placeholder
    await ReportAnalysis.findOneAndUpdate(
      { campaignId, reportType },
      { $set: { status: 'generating' } },
      { upsert: true }
    );

    try {
      const result = await generateAnalysis(campaign, records, reportType);
      const questions = (QUESTIONS_MAP[reportType] || []).map((q) => {
        const answered = (result.questions || []).find(a => a.id === q.id);
        return {
          ...q,
          answer: answered?.answer || { sections: [{ type: 'summary', text: 'Chưa có phân tích cho câu hỏi này.' }] },
        };
      });

      await ReportAnalysis.findOneAndUpdate(
        { campaignId, reportType },
        {
          $set: {
            status: 'ready',
            overall: result.overall || '',
            questions,
            generatedAt: new Date(),
            error: '',
          },
        }
      );
      console.log(`[reportGen] Analysis ready: ${reportType} for ${campaignId}`);
    } catch (err) {
      console.error(`[reportGen] Analysis failed for ${reportType}:`, err.message);
      await ReportAnalysis.findOneAndUpdate(
        { campaignId, reportType },
        { $set: { status: 'error', error: err.message } }
      );
    }
  });

  await Promise.allSettled(analysisPromises);
  console.log(`[reportGen] All analyses complete for ${campaignId}`);
}

// ─── Get generation status ───────────────────────────────────────────────────
async function getReportStatus(campaignId) {
  const docs = await ReportAnalysis.find({ campaignId }).lean();
  const status = {};
  for (const rt of REPORT_TYPES) {
    const doc = docs.find(d => d.reportType === rt);
    status[rt] = doc?.status || 'pending';
  }
  const ready = Object.values(status).filter(s => s === 'ready').length;
  const errors = Object.values(status).filter(s => s === 'error').length;
  return { campaignId, total: REPORT_TYPES.length, ready, errors, types: status };
}

module.exports = {
  generateReports, getReportStatus, REPORT_TYPES, QUESTIONS_MAP,
  buildOpenAIRequestBody,
};
