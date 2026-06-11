/**
 * awareness/a3-matrix.js
 * A3 — Audience/Channel Performance Matrix Table
 * Rows: channel · Columns: Reach, Reach%, Freq, CPM, VI, Spend share
 * Decision rule: Low VI + high CPM = deprioritize · Low Freq + high Reach = scale
 */

export function renderMatrix(rows, utils) {
  const { fmt, fmtVND } = utils;
  const container = document.getElementById('aw-matrix');
  if (!container) return;

  const totImp   = rows.reduce((s, r) => s + r.impressions, 0);
  const totReach = rows.reduce((s, r) => s + r.reach, 0);
  const totSpend = rows.reduce((s, r) => s + r.spend, 0);

  // Group by channel (audience proxy)
  const channelMap = {};
  rows.forEach(r => {
    const ch = r.channel || r.audience || 'Unknown';
    if (!channelMap[ch]) channelMap[ch] = { imp: 0, reach: 0, spend: 0, viSum: 0, cpmSum: 0, conv: 0, n: 0 };
    channelMap[ch].imp    += r.impressions;
    channelMap[ch].reach  += r.reach;
    channelMap[ch].spend  += r.spend;
    channelMap[ch].viSum  += r.vi * r.impressions;
    channelMap[ch].cpmSum += r.cpm;
    channelMap[ch].conv   += r.conversions;
    channelMap[ch].n++;
  });

  const rows2 = Object.entries(channelMap).map(([ch, d]) => ({
    channel:    ch,
    imp:        d.imp,
    reach:      d.reach,
    reachPct:   totImp > 0 ? d.imp / totImp * 100 : 0,
    freq:       d.reach > 0 ? d.imp / d.reach : 0,
    cpm:        d.n > 0 ? d.cpmSum / d.n : 0,
    vi:         d.imp > 0 ? d.viSum / d.imp : 0,
    spend:      d.spend,
    spendPct:   totSpend > 0 ? d.spend / totSpend * 100 : 0,
    conv:       d.conv
  })).sort((a, b) => b.imp - a.imp);

  const pill = (val, good, warn) => {
    const cls = val >= good ? 'good' : val >= warn ? 'watch' : 'bad';
    return `<span class="pill ${cls}">${val.toFixed(1)}%</span>`;
  };

  const freqPill = f => {
    const cls = f <= 3 ? 'good' : f <= 5 ? 'watch' : 'bad';
    return `<span class="pill ${cls}">${f.toFixed(2)}x</span>`;
  };

  container.innerHTML = `
    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>Channel</th>
            <th class="num">Impressions</th>
            <th class="num">Reach</th>
            <th class="num">Imp%</th>
            <th class="num">Frequency</th>
            <th class="num">Avg CPM</th>
            <th class="num">VI</th>
            <th class="num">Spend</th>
            <th class="num">Spend%</th>
            <th class="num">Conv.</th>
          </tr>
        </thead>
        <tbody>
          ${rows2.map(r => `
            <tr>
              <td class="lab">${r.channel}</td>
              <td class="num">${fmt(r.imp)}</td>
              <td class="num">${fmt(r.reach)}</td>
              <td class="num">${r.reachPct.toFixed(1)}%</td>
              <td class="num">${freqPill(r.freq)}</td>
              <td class="num">₫${Math.round(r.cpm).toLocaleString('vi-VN')}</td>
              <td class="num">${pill(r.vi, 70, 50)}</td>
              <td class="num">${fmtVND(r.spend)}</td>
              <td class="num">${r.spendPct.toFixed(1)}%</td>
              <td class="num">${fmt(r.conv)}</td>
            </tr>`).join('')}
        </tbody>
        <tfoot>
          <tr style="font-weight:700;background:#f8fafc">
            <td class="lab">TOTAL</td>
            <td class="num">${fmt(totImp)}</td>
            <td class="num">${fmt(totReach)}</td>
            <td class="num">100%</td>
            <td class="num">${totReach > 0 ? (totImp / totReach).toFixed(2) + 'x' : '—'}</td>
            <td class="num">—</td>
            <td class="num">—</td>
            <td class="num">${fmtVND(totSpend)}</td>
            <td class="num">100%</td>
            <td class="num">${fmt(rows.reduce((s, r) => s + r.conversions, 0))}</td>
          </tr>
        </tfoot>
      </table>
    </div>`;

  // Insight
  const ic  = document.getElementById('ic_aw_matrix');
  const ins = document.getElementById('ins_aw_matrix');
  if (ic && ins && rows2.length > 0) {
    const best = [...rows2].sort((a, b) => b.vi - a.vi)[0];
    const worst = [...rows2].sort((a, b) => a.vi - b.vi)[0];
    ic.className = 'insight-ic'; ic.textContent = 'i';
    ins.innerHTML = `<b>${best.channel}</b> leads on viewability (VI ${best.vi.toFixed(0)}%). <b>${worst.channel}</b> has the lowest VI (${worst.vi.toFixed(0)}%) — evaluate for budget reallocation.`;
  }
}
