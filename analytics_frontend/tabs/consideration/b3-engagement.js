/**
 * consideration/b3-engagement.js
 * B3 — CTR by Channel/Format (grouped bar) + Campaign Engagement Ranking table
 * Use-case: Which format and channel drives the most engagement? Which campaign wins?
 */

function el(id) { return document.getElementById(id); }
function destroyIfExists(id) {
  const c = document.getElementById(id);
  if (c) { const ch = Chart.getChart(c); if (ch) ch.destroy(); }
}

/* ── B3-a: CTR by Channel × Format grouped bar ──────────────────── */
export function drawCtrByFormat(rows, utils) {
  const { alpha, COLORS, registerChart } = utils;
  destroyIfExists('ch_co_ctr_fmt');

  const channels = [...new Set(rows.map(r => r.channel).filter(Boolean))];
  const formats  = [...new Set(rows.map(r => r.format).filter(Boolean))];

  // datasets = one per format; labels = channels
  const datasets = formats.map((fmt, i) => {
    const color = COLORS[i % COLORS.length];
    const data = channels.map(ch => {
      const recs = rows.filter(r => r.channel === ch && r.format === fmt);
      const imp = recs.reduce((s, r) => s + r.impressions, 0);
      const clk = recs.reduce((s, r) => s + r.clicks, 0);
      return imp > 0 ? +(clk / imp * 100).toFixed(3) : 0;
    });
    return {
      label: fmt,
      data,
      backgroundColor: alpha(color, 0.8),
      borderRadius: 4
    };
  });

  const canvas = el('ch_co_ctr_fmt');
  if (!canvas) return;

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: { labels: channels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { font: { size: 11 }, boxWidth: 14 } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.raw.toFixed(2)}%` } }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 11 } } },
        y: { ticks: { font: { size: 10 }, callback: v => v.toFixed(2) + '%' } }
      }
    }
  });
  registerChart('ch_co_ctr_fmt', chart);

  // Insight
  const ic = el('ic_co_ctr_fmt'), ins = el('ins_co_ctr_fmt');
  if (ic && ins) {
    // Find best channel+format combo
    let best = { ch: '', fmt: '', ctr: 0 };
    channels.forEach(ch => {
      formats.forEach(f => {
        const recs = rows.filter(r => r.channel === ch && r.format === f);
        const imp = recs.reduce((s, r) => s + r.impressions, 0);
        const clk = recs.reduce((s, r) => s + r.clicks, 0);
        const ctr = imp > 0 ? clk / imp * 100 : 0;
        if (ctr > best.ctr) best = { ch, fmt: f, ctr };
      });
    });
    ic.className = 'insight-ic good'; ic.textContent = '✓';
    ins.innerHTML = `Best combination: <b>${best.fmt}</b> on <b>${best.ch}</b> with CTR <b>${best.ctr.toFixed(2)}%</b>. Prioritise this channel-format pairing for engagement-focused campaigns.`;
  }
}

/* ── B3-b: Campaign Engagement Ranking table ─────────────────────── */
export function renderCampaignRanking(rows, utils) {
  const { fmt, fmtVND } = utils;
  const container = el('co-camp-ranking');
  if (!container) return;

  const campMap = {};
  rows.forEach(r => {
    const camp = r.campaignId || 'Unknown';
    if (!campMap[camp]) campMap[camp] = { imp: 0, clk: 0, spend: 0, conv: 0, reach: 0 };
    campMap[camp].imp   += r.impressions;
    campMap[camp].clk   += r.clicks;
    campMap[camp].spend += r.spend;
    campMap[camp].conv  += r.conversions;
    campMap[camp].reach += r.reach;
  });

  const sorted = Object.entries(campMap)
    .map(([camp, d]) => ({
      camp,
      imp:   d.imp,
      clk:   d.clk,
      ctr:   d.imp > 0 ? d.clk / d.imp * 100 : 0,
      spend: d.spend,
      cpc:   d.clk > 0 ? d.spend / d.clk : 0,
      conv:  d.conv,
      reach: d.reach,
      cvr:   d.clk > 0 ? d.conv / d.clk * 100 : 0
    }))
    .sort((a, b) => b.ctr - a.ctr);

  const pillCtr = ctr => {
    const cls = ctr >= 0.8 ? 'good' : ctr >= 0.4 ? 'watch' : 'bad';
    return `<span class="pill ${cls}">${ctr.toFixed(2)}%</span>`;
  };

  const medal = i => i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `${i + 1}`;

  container.innerHTML = `
    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Campaign</th>
            <th class="num">Impressions</th>
            <th class="num">Clicks</th>
            <th class="num">CTR ↓</th>
            <th class="num">Reach</th>
            <th class="num">Spend</th>
            <th class="num">CPC</th>
            <th class="num">Conv.</th>
            <th class="num">CVR</th>
          </tr>
        </thead>
        <tbody>
          ${sorted.map((r, i) => `
            <tr>
              <td class="ctr">${medal(i)}</td>
              <td class="lab">${r.camp}</td>
              <td class="num">${fmt(r.imp)}</td>
              <td class="num">${fmt(r.clk)}</td>
              <td class="num">${pillCtr(r.ctr)}</td>
              <td class="num">${fmt(r.reach)}</td>
              <td class="num">${fmtVND(r.spend)}</td>
              <td class="num">${fmtVND(r.cpc)}</td>
              <td class="num">${fmt(r.conv)}</td>
              <td class="num">${r.cvr.toFixed(2)}%</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  const ic = el('ic_co_ranking'), ins = el('ins_co_ranking');
  if (ic && ins && sorted.length > 0) {
    const top = sorted[0];
    ic.className = 'insight-ic good'; ic.textContent = '🥇';
    ins.innerHTML = `<b>${top.camp}</b> leads on CTR at <b>${top.ctr.toFixed(2)}%</b> with <b>${fmt(top.clk)}</b> total clicks and CVR of <b>${top.cvr.toFixed(2)}%</b>.`;
  }
}
