/**
 * tabs/daily-ops.js — Daily Ops tab renderer
 * 3 charts: Combo (Imp+Click+CTR), Audience grouped bars, Campaign comparison multi-line
 * Plus OPS scorecard at top
 */

/* ── Helpers ─────────────────────────────────────────────────────── */
function el(id) { return document.getElementById(id); }

function norm(r) {
  // Real backend schema: campaignId, placementId, channel, format, impressions, clicks,
  // spend, ctr, cpm, reach, conversions, vi, date
  // Mock schema: brand, zone, 'Audience Segment', 'Spend VND', etc.
  const campaignId = r.campaignId || r['Campaign ID'] || '';
  const placementId = r.placementId || r.zone || r.Zone || '';
  const channel = r.channel || '';
  // Derive a "brand" label from campaignId prefix or Brand field
  const brand = r.brand || r.Brand || campaignId.replace(/-\d+$/, '') || 'Unknown';
  // Audience comes from mock data or fall back to channel
  const audience = r.audienceSegment || r['Audience Segment'] || channel || 'Unknown';

  return {
    date:          r.date         || r.Date         || '',
    brand,
    zone:          placementId,
    channel,
    campaignId,
    audience,
    impressions:   Number(r.impressions  || r.Impressions  || 0),
    reach:         Number(r.reach        || r.Reach        || 0),
    clicks:        Number(r.clicks       || r.Clicks       || 0),
    ctr:           Number(r.ctr          || r.CTR          || 0),
    spend:         Number(r.spend        || r.spendVnd     || r['Spend VND'] || 0),
    cpm:           Number(r.cpm          || r.CPM          || 0),
    conversions:   Number(r.conversions  || r.Conversions  || 0),
    cvr:           Number(r.cvr          || r.CVR          || 0),
    roas:          Number(r.roas         || r.ROAS         || 0),
    vi:            Number(r.vi           || 0),
    verdict:       r.verdict      || r.Verdict      || '',
    creative:      r.creativeId   || r['Creative ID'] || '',
    msgAngle:      r.messageAngle || r['Message Angle'] || '',
    engagements:   Number(r.engagements  || r.Engagements  || 0),
    engRate:       Number(r.engagementRate || r['Engagement Rate'] || 0),
  };
}


/* ── Render entry point ──────────────────────────────────────────── */
export function render(State, utils) {
  const panel = el('p-op');

  const data = (State.filtered.length > 0 || hasActiveFilter(State.filters))
    ? State.filtered
    : State.allData;

  const rows = data.map(norm);

  panel.innerHTML = buildHTML(rows, utils);

  // Wire controls before drawing
  bindControls(rows, utils);

  // Draw all 3 charts
  drawCombo(rows, utils);
  drawAudience(rows, 'impressions', utils);
  drawCompare(rows, 'CTR', 'Brand', utils);
}

export function destroy() {
  // Charts cleaned up via registerChart in app.js
}

function hasActiveFilter(f) {
  return f.brand || f.zone || f.audience || f.startDate || f.endDate;
}

/* ── HTML skeleton ───────────────────────────────────────────────── */
function buildHTML(rows, utils) {
  const scorecard = buildScorecard(rows, utils);
  return `
    <!-- OPS Scorecard -->
    <div class="scorecard" id="sc-op">${scorecard}</div>

    <!-- Section header -->
    <div class="section-h"><span class="uc">OPS</span> Daily Monitoring · Standard Ad Ops View</div>

    <!-- Chart 1: Daily Combo -->
    <div class="grid wide">
      <div class="card">
        <div class="card-head">
          <span class="badge op">OPS</span>
          <div>
            <h3>Campaign Performance — Daily Combo</h3>
            <div class="sub">Impressions + Clicks (bars) · CTR % (line)</div>
          </div>
        </div>
        <div class="card-usecase"><b>When to use:</b> Default ad-ops view. Check daily delivery volume, reach, clicks and CTR at a glance.</div>
        <div class="card-rule"><b>Decision rule:</b> Flat impressions + dropping CTR = creative fatigue. Large gap between impressions and reach = over-frequency.</div>
        <div class="card-body auto" style="padding-bottom:16px">
          <div class="ctrl-row">
            <span class="ctrl-label">Campaign:</span>
            <select id="op-camp-sel"><option value="">All (aggregate)</option></select>
            <span class="ctrl-note" id="op-camp-stat">—</span>
          </div>
          <div class="chart-wrap tall"><canvas id="ch_op_combo"></canvas></div>
        </div>
        <div class="card-insight">
          <span class="insight-ic" id="ic_op_combo">i</span>
          <span id="ins_op_combo">—</span>
        </div>
      </div>
    </div>

    <!-- Chart 2: Audience grouped -->
    <div class="grid wide">
      <div class="card">
        <div class="card-head">
          <span class="badge op">OPS</span>
          <div>
            <h3>Performance by Audience Segment</h3>
            <div class="sub">Grouped bars per date · toggle metric · top 4 audiences by spend</div>
          </div>
        </div>
        <div class="card-usecase"><b>When to use:</b> Compare audience segments day-by-day — which segment delivers most, which engages best.</div>
        <div class="card-rule"><b>Decision rule:</b> Dominant impressions but low CTR = audience-creative mismatch. High CTR but low volume = scale this audience.</div>
        <div class="card-body auto" style="padding-bottom:16px">
          <div class="ctrl-row">
            <span class="ctrl-label">Metric:</span>
            <div class="toggle-group" id="aud-toggle">
              <button class="toggle-btn on" data-metric="impressions">Impression</button>
              <button class="toggle-btn" data-metric="clicks">Click</button>
              <button class="toggle-btn" data-metric="ctr">CTR</button>
            </div>
            <span class="ctrl-note">Top 4 audiences by spend</span>
          </div>
          <div class="chart-wrap tall"><canvas id="ch_op_audience"></canvas></div>
        </div>
        <div class="card-insight">
          <span class="insight-ic" id="ic_op_audience">i</span>
          <span id="ins_op_audience">—</span>
        </div>
      </div>
    </div>

    <!-- Chart 3: Campaign comparison multi-line -->
    <div class="grid wide">
      <div class="card">
        <div class="card-head">
          <span class="badge op">OPS</span>
          <div>
            <h3>Campaign Comparison — Multi-line over Time</h3>
            <div class="sub">Compare up to 5 entities on 1 metric · top 5 by total volume</div>
          </div>
        </div>
        <div class="card-usecase"><b>When to use:</b> Compare campaigns or segments on the same tab — who is outperforming, whose trend is declining.</div>
        <div class="card-rule"><b>Decision rule:</b> Trend down &gt; 2× baseline → fatigue. Steady + above baseline = winner to scale.</div>
        <div class="card-body auto" style="padding-bottom:16px">
          <div class="ctrl-row">
            <span class="ctrl-label">Metric:</span>
            <select id="cmp-metric-sel">
              <option value="impressions">Impressions</option>
              <option value="clicks">Clicks</option>
              <option value="ctr" selected>CTR</option>
              <option value="cvr">CVR</option>
              <option value="roas">ROAS</option>
              <option value="cpm">CPM</option>
            </select>
            <span class="ctrl-label" style="margin-left:10px">Compare by:</span>
            <select id="cmp-by-sel">
              <option value="Brand" selected>Brand</option>
              <option value="Zone">Zone</option>
              <option value="Audience">Audience</option>
              <option value="Creative">Creative</option>
              <option value="Angle">Message Angle</option>
            </select>
            <span class="ctrl-note">Top 5 by total volume</span>
          </div>
          <div class="chart-wrap tall"><canvas id="ch_op_compare"></canvas></div>
        </div>
        <div class="card-insight">
          <span class="insight-ic" id="ic_op_compare">i</span>
          <span id="ins_op_compare">—</span>
        </div>
      </div>
    </div>
  `;
}

/* ── Scorecard ───────────────────────────────────────────────────── */
function buildScorecard(rows, utils) {
  const { fmt, fmtPct, fmtVND, fmtK } = utils;
  const totImp   = rows.reduce((s,r) => s + r.impressions, 0);
  const totClk   = rows.reduce((s,r) => s + r.clicks, 0);
  const totSpend = rows.reduce((s,r) => s + r.spend, 0);
  const avgCTR   = totImp > 0 ? totClk / totImp : 0;
  const avgCPM   = rows.length > 0 ? rows.reduce((s,r) => s + r.cpm, 0) / rows.length : 0;

  const good = rows.filter(r => r.verdict === 'good').length;
  const bad  = rows.filter(r => r.verdict === 'bad').length;
  const goodPct = rows.length > 0 ? (good / rows.length * 100).toFixed(0) : '—';

  const kpis = [
    { label: 'Impressions', val: fmtK(totImp),        delta: null },
    { label: 'Clicks',      val: fmtK(totClk),         delta: null },
    { label: 'Avg CTR',     val: fmtPct(avgCTR),       delta: null },
    { label: 'Total Spend', val: fmtVND(totSpend),     delta: null },
    { label: 'Avg CPM',     val: '₫' + Math.round(avgCPM).toLocaleString('vi-VN'), delta: null },
    { label: '✅ Good',     val: good + ' campaigns',  delta: `${goodPct}% pass rate`, cls: 'good' },
    { label: '❌ Bad',      val: bad  + ' campaigns',  delta: null, cls: bad > good ? 'bad' : 'neutral' },
  ];

  return kpis.map(k => `
    <div class="sc-item">
      <div class="sc-label">${k.label}</div>
      <div class="sc-val">${k.val}</div>
      ${k.delta ? `<div class="sc-delta ${k.cls || ''}">${k.delta}</div>` : ''}
    </div>
  `).join('');
}

/* ── Chart 1: Daily Combo ────────────────────────────────────────── */
function drawCombo(rows, utils, campFilter = '') {
  const { fmt, fmtPct, registerChart, alpha } = utils;

  destroyIfExists('ch_op_combo');

  let filtered = campFilter ? rows.filter(r => r.campaignId === campFilter) : rows;

  // Group by date
  const dateMap = {};
  filtered.forEach(r => {
    if (!dateMap[r.date]) dateMap[r.date] = { imp: 0, clk: 0, spend: 0, n: 0 };
    dateMap[r.date].imp   += r.impressions;
    dateMap[r.date].clk   += r.clicks;
    dateMap[r.date].spend += r.spend;
    dateMap[r.date].n++;
  });

  const dates = Object.keys(dateMap).sort();
  const imps  = dates.map(d => dateMap[d].imp);
  const clks  = dates.map(d => dateMap[d].clk);
  const ctrs  = dates.map(d => dateMap[d].imp > 0 ? (dateMap[d].clk / dateMap[d].imp * 100) : 0);

  const canvas = el('ch_op_combo');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  const chart = new Chart(ctx, {
    data: {
      labels: dates.map(d => d.slice(5)), // MM-DD
      datasets: [
        {
          type: 'bar',
          label: 'Impressions',
          data: imps,
          backgroundColor: alpha('#1f3551', 0.75),
          yAxisID: 'y',
          order: 2
        },
        {
          type: 'bar',
          label: 'Clicks',
          data: clks,
          backgroundColor: alpha('#2c7fb8', 0.8),
          yAxisID: 'y',
          order: 2
        },
        {
          type: 'line',
          label: 'CTR %',
          data: ctrs,
          borderColor: '#c98a14',
          backgroundColor: alpha('#c98a14', 0.12),
          borderWidth: 2.5,
          pointRadius: 3,
          pointBackgroundColor: '#c98a14',
          fill: false,
          tension: 0.3,
          yAxisID: 'y2',
          order: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { font: { size: 11 }, boxWidth: 14 } },
        tooltip: {
          callbacks: {
            label: ctx => {
              if (ctx.dataset.label === 'CTR %') return ' CTR: ' + ctx.raw.toFixed(2) + '%';
              return ` ${ctx.dataset.label}: ${fmt(ctx.raw)}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: 'Volume', font: { size: 10 } },
          ticks: { font: { size: 10 }, callback: v => fmtK_local(v) }
        },
        y2: {
          type: 'linear',
          position: 'right',
          title: { display: true, text: 'CTR %', font: { size: 10 } },
          grid: { drawOnChartArea: false },
          ticks: { font: { size: 10 }, callback: v => v.toFixed(2) + '%' }
        }
      }
    }
  });

  registerChart('ch_op_combo', chart);

  // Update campaign stat + insight
  const totImp = imps.reduce((s,v) => s+v, 0);
  const totClk = clks.reduce((s,v) => s+v, 0);
  const avgCTR = totImp > 0 ? (totClk / totImp * 100) : 0;
  const el2 = el('op-camp-stat');
  if (el2) el2.textContent = `${dates.length} days · ${fmt(totImp)} imps · CTR ${avgCTR.toFixed(2)}%`;

  // Insight
  const ctrLast3 = ctrs.slice(-3);
  const ctrFirst3 = ctrs.slice(0, 3);
  const avgLast = ctrLast3.reduce((s,v) => s+v,0) / (ctrLast3.length||1);
  const avgFirst = ctrFirst3.reduce((s,v) => s+v,0) / (ctrFirst3.length||1);
  const ic = el('ic_op_combo');
  const ins = el('ins_op_combo');
  if (ic && ins) {
    if (avgLast < avgFirst * 0.8) {
      ic.className = 'insight-ic bad'; ic.textContent = '▼';
      ins.innerHTML = `<b>CTR declining</b> — last 3 days avg ${avgLast.toFixed(2)}% vs opening ${avgFirst.toFixed(2)}%. Possible creative fatigue. Consider refreshing creative assets.`;
    } else if (avgLast > avgFirst * 1.1) {
      ic.className = 'insight-ic good'; ic.textContent = '▲';
      ins.innerHTML = `<b>CTR improving</b> — last 3 days avg ${avgLast.toFixed(2)}% vs opening ${avgFirst.toFixed(2)}%. Campaign is gaining momentum.`;
    } else {
      ic.className = 'insight-ic'; ic.textContent = 'i';
      ins.innerHTML = `CTR stable around <b>${avgLast.toFixed(2)}%</b>. Total <b>${fmt(totImp)}</b> impressions, <b>${fmt(totClk)}</b> clicks across <b>${dates.length}</b> days.`;
    }
  }
}

/* ── Chart 2: Audience grouped bars ─────────────────────────────── */
function drawAudience(rows, metric, utils) {
  const { fmt, registerChart, alpha, COLORS } = utils;

  destroyIfExists('ch_op_audience');

  // Top 4 audiences by spend
  const audSpend = {};
  rows.forEach(r => {
    audSpend[r.audience] = (audSpend[r.audience] || 0) + r.spend;
  });
  const top4 = Object.entries(audSpend)
    .sort((a,b) => b[1]-a[1])
    .slice(0,4)
    .map(e => e[0])
    .filter(Boolean);

  // Dates
  const dates = [...new Set(rows.map(r => r.date))].sort();

  const datasets = top4.map((aud, i) => {
    const color = COLORS[i % COLORS.length];
    const data = dates.map(d => {
      const recs = rows.filter(r => r.date === d && r.audience === aud);
      if (!recs.length) return 0;
      if (metric === 'impressions') return recs.reduce((s,r) => s+r.impressions,0);
      if (metric === 'clicks')      return recs.reduce((s,r) => s+r.clicks,0);
      if (metric === 'ctr') {
        const imp = recs.reduce((s,r) => s+r.impressions,0);
        const clk = recs.reduce((s,r) => s+r.clicks,0);
        return imp > 0 ? clk/imp*100 : 0;
      }
      return 0;
    });
    return { label: aud, data, backgroundColor: alpha(color, 0.8) };
  });

  const canvas = el('ch_op_audience');
  if (!canvas) return;

  const isCTR = metric === 'ctr';
  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: { labels: dates.map(d => d.slice(5)), datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { font: { size: 11 }, boxWidth: 14 } },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${isCTR ? ctx.raw.toFixed(2)+'%' : fmt(ctx.raw)}`
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: {
          ticks: {
            font: { size: 10 },
            callback: v => isCTR ? v.toFixed(1)+'%' : fmtK_local(v)
          }
        }
      }
    }
  });

  registerChart('ch_op_audience', chart);

  // Insight
  const ic = el('ic_op_audience');
  const ins = el('ins_op_audience');
  if (ic && ins && top4.length > 0) {
    const audTotals = top4.map(aud => ({
      aud,
      imp: rows.filter(r=>r.audience===aud).reduce((s,r)=>s+r.impressions,0),
      clk: rows.filter(r=>r.audience===aud).reduce((s,r)=>s+r.clicks,0),
    }));
    const topCTR = audTotals.sort((a,b) => (b.clk/Math.max(b.imp,1)) - (a.clk/Math.max(a.imp,1)))[0];
    ic.className = 'insight-ic good'; ic.textContent = '✓';
    ins.innerHTML = `<b>${topCTR.aud}</b> leads with the highest CTR (${(topCTR.clk/Math.max(topCTR.imp,1)*100).toFixed(2)}%) among the top 4 audiences. Consider increasing budget allocation to this segment.`;
  }
}

/* ── Chart 3: Campaign comparison multi-line ─────────────────────── */
function drawCompare(rows, metric, compareBy, utils) {
  const { fmt, registerChart, alpha, COLORS } = utils;

  destroyIfExists('ch_op_compare');

  const getKey = (r) => {
    if (compareBy === 'Brand')    return r.brand;
    if (compareBy === 'Zone')     return r.zone;
    if (compareBy === 'Audience') return r.audience;
    if (compareBy === 'Creative') return r.creative;
    if (compareBy === 'Angle')    return r.msgAngle;
    return r.brand;
  };

  const getValue = (recs) => {
    if (metric === 'impressions') return recs.reduce((s,r)=>s+r.impressions,0);
    if (metric === 'clicks')      return recs.reduce((s,r)=>s+r.clicks,0);
    if (metric === 'ctr') {
      const imp = recs.reduce((s,r)=>s+r.impressions,0);
      const clk = recs.reduce((s,r)=>s+r.clicks,0);
      return imp>0 ? clk/imp*100 : 0;
    }
    if (metric === 'cvr') {
      const clk = recs.reduce((s,r)=>s+r.clicks,0);
      const conv = recs.reduce((s,r)=>s+(r.cvr*r.clicks||0),0);
      return clk>0 ? conv/clk*100 : 0;
    }
    if (metric === 'roas') return recs.reduce((s,r)=>s+r.roas,0)/Math.max(recs.length,1);
    if (metric === 'cpm')  return recs.reduce((s,r)=>s+r.cpm,0)/Math.max(recs.length,1);
    return 0;
  };

  // Top 5 keys by total impressions
  const keyTotals = {};
  rows.forEach(r => { const k = getKey(r); if(k) keyTotals[k]=(keyTotals[k]||0)+r.impressions; });
  const top5 = Object.entries(keyTotals).sort((a,b)=>b[1]-a[1]).slice(0,5).map(e=>e[0]);

  const dates = [...new Set(rows.map(r=>r.date))].sort();

  const datasets = top5.map((key, i) => {
    const color = COLORS[i % COLORS.length];
    const data = dates.map(d => {
      const recs = rows.filter(r => r.date===d && getKey(r)===key);
      return recs.length ? getValue(recs) : null;
    });
    return {
      label: key,
      data,
      borderColor: color,
      backgroundColor: alpha(color, 0.1),
      borderWidth: 2.5,
      pointRadius: 3,
      tension: 0.3,
      fill: false,
      spanGaps: true
    };
  });

  const canvas = el('ch_op_compare');
  if (!canvas) return;

  const isPct = ['ctr','cvr'].includes(metric);
  const isVND = metric === 'cpm';

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: { labels: dates.map(d=>d.slice(5)), datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { font: { size: 11 }, boxWidth: 14 } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const v = ctx.raw;
              if (v===null) return null;
              if (isPct) return ` ${ctx.dataset.label}: ${v.toFixed(2)}%`;
              if (isVND) return ` ${ctx.dataset.label}: ₫${Math.round(v).toLocaleString('vi-VN')}`;
              return ` ${ctx.dataset.label}: ${fmt(v)}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: {
          ticks: {
            font: { size: 10 },
            callback: v => isPct ? v.toFixed(1)+'%' : fmtK_local(v)
          }
        }
      }
    }
  });

  registerChart('ch_op_compare', chart);

  // Insight
  const ic = el('ic_op_compare');
  const ins = el('ins_op_compare');
  if (ic && ins && top5.length > 0) {
    ic.className = 'insight-ic'; ic.textContent = 'i';
    ins.innerHTML = `Comparing <b>${compareBy}</b> on <b>${metric.toUpperCase()}</b> — top 5 entities by impression volume. <b>${top5[0]}</b> leads overall.`;
  }
}

/* ── Controls binding ────────────────────────────────────────────── */
function bindControls(rows, utils) {
  // Campaign selector
  const campSel = el('op-camp-sel');
  if (campSel) {
    const camps = [...new Set(rows.map(r=>r.campaignId).filter(Boolean))].sort();
    camps.forEach(c => {
      const o = document.createElement('option');
      o.value = c; o.textContent = c;
      campSel.appendChild(o);
    });
    campSel.addEventListener('change', () => {
      drawCombo(rows, utils, campSel.value);
    });
  }

  // Audience toggle
  const audToggle = el('aud-toggle');
  if (audToggle) {
    audToggle.addEventListener('click', e => {
      const btn = e.target.closest('[data-metric]');
      if (!btn) return;
      audToggle.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('on'));
      btn.classList.add('on');
      drawAudience(rows, btn.dataset.metric, utils);
    });
  }

  // Compare metric + by selectors
  const metricSel = el('cmp-metric-sel');
  const bySel     = el('cmp-by-sel');

  const redrawCompare = () => {
    if (metricSel && bySel) drawCompare(rows, metricSel.value, bySel.value, utils);
  };

  if (metricSel) metricSel.addEventListener('change', redrawCompare);
  if (bySel)     bySel.addEventListener('change', redrawCompare);
}

/* ── Local helpers ───────────────────────────────────────────────── */
function fmtK_local(v) {
  if (v >= 1_000_000) return (v/1_000_000).toFixed(1)+'M';
  if (v >= 1_000)     return (v/1_000).toFixed(0)+'K';
  return String(Math.round(v));
}

function destroyIfExists(id) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();
}
