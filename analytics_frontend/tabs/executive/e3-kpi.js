/**
 * executive/e3-kpi.js
 * E3 — Period-over-Period KPI Comparison Table (First half vs Second half)
 * Use-case: Is performance improving or degrading over the campaign run?
 */

export function renderPoPTable(rows, utils) {
  const { fmt, fmtVND } = utils;
  const container = document.getElementById('ex-pop-table');
  if (!container) return;

  // Split rows into first vs second half by date
  const dates = [...new Set(rows.map(r => r.date).filter(Boolean))].sort();
  const mid   = Math.floor(dates.length / 2);
  const firstDates = new Set(dates.slice(0, mid));
  const lastDates  = new Set(dates.slice(mid));

  const agg = (dateSet) => {
    const recs = rows.filter(r => dateSet.has(r.date));
    const imp   = recs.reduce((s, r) => s + r.impressions, 0);
    const reach = recs.reduce((s, r) => s + r.reach, 0);
    const clk   = recs.reduce((s, r) => s + r.clicks, 0);
    const conv  = recs.reduce((s, r) => s + r.conversions, 0);
    const spend = recs.reduce((s, r) => s + r.spend, 0);
    const vi    = recs.length > 0 ? recs.reduce((s, r) => s + r.vi, 0) / recs.length : 0;
    return {
      imp, reach, clk, conv, spend, vi,
      ctr: imp  > 0 ? clk  / imp  * 100 : 0,
      cvr: clk  > 0 ? conv / clk  * 100 : 0,
      cpa: conv > 0 ? spend / conv : 0,
      cpm: recs.length > 0 ? recs.reduce((s, r) => s + r.cpm, 0) / recs.length : 0,
      freq: reach > 0 ? imp / reach : 0,
    };
  };

  const p1 = agg(firstDates);
  const p2 = agg(lastDates);

  const delta = (v2, v1, higherIsBetter = true) => {
    if (!v1) return { pct: '—', cls: '' };
    const pct = (v2 - v1) / v1 * 100;
    const isGood = higherIsBetter ? pct >= 0 : pct <= 0;
    const cls = Math.abs(pct) < 2 ? '' : isGood ? 'good' : 'bad';
    return { pct: (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%', cls };
  };

  const metrics = [
    { name: 'Impressions',    f: d => fmt(d.imp),               d: delta(p2.imp,   p1.imp),   hi: true },
    { name: 'Reach',          f: d => fmt(d.reach),             d: delta(p2.reach, p1.reach), hi: true },
    { name: 'Clicks',         f: d => fmt(d.clk),               d: delta(p2.clk,   p1.clk),   hi: true },
    { name: 'CTR %',          f: d => d.ctr.toFixed(3) + '%',   d: delta(p2.ctr,   p1.ctr),   hi: true },
    { name: 'Avg Frequency',  f: d => d.freq.toFixed(2) + 'x',  d: delta(p2.freq,  p1.freq,  false), hi: false },
    { name: 'Conversions',    f: d => fmt(d.conv),              d: delta(p2.conv,  p1.conv),  hi: true },
    { name: 'CVR %',          f: d => d.cvr.toFixed(3) + '%',   d: delta(p2.cvr,   p1.cvr),   hi: true },
    { name: 'Total Spend',    f: d => fmtVND(d.spend),          d: delta(p2.spend, p1.spend,  false), hi: false },
    { name: 'Avg CPM',        f: d => fmtVND(d.cpm),            d: delta(p2.cpm,   p1.cpm,   false), hi: false },
    { name: 'CPA',            f: d => fmtVND(d.cpa),            d: delta(p2.cpa,   p1.cpa,   false), hi: false },
    { name: 'Avg VI %',       f: d => d.vi.toFixed(1) + '%',    d: delta(p2.vi,    p1.vi),    hi: true },
  ];

  const p1Label = `Period 1 (${dates[0]?.slice(5)} – ${dates[mid - 1]?.slice(5)})`;
  const p2Label = `Period 2 (${dates[mid]?.slice(5)} – ${dates[dates.length - 1]?.slice(5)})`;

  container.innerHTML = `
    <div class="tbl-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>Metric</th>
            <th class="num">${p1Label}</th>
            <th class="num">${p2Label}</th>
            <th class="num">Δ Change</th>
            <th>Signal</th>
          </tr>
        </thead>
        <tbody>
          ${metrics.map(m => `
            <tr>
              <td class="lab" style="font-weight:600">${m.name}</td>
              <td class="num" style="color:var(--muted)">${m.f(p1)}</td>
              <td class="num" style="font-weight:700">${m.f(p2)}</td>
              <td class="num"><span class="pill ${m.d.cls}">${m.d.pct}</span></td>
              <td style="font-size:11px;color:var(--muted)">
                ${m.d.cls === 'good' ? '✔ Improving' : m.d.cls === 'bad' ? '✘ Declining' : '→ Stable'}
              </td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  const ic = el('ic_ex_pop'), ins = el('ins_ex_pop');
  const el2 = id => document.getElementById(id);
  const icEl = el2('ic_ex_pop'), insEl = el2('ins_ex_pop');
  if (icEl && insEl) {
    const improving = metrics.filter(m => m.d.cls === 'good').length;
    const declining = metrics.filter(m => m.d.cls === 'bad').length;
    icEl.className = declining > improving ? 'insight-ic bad' : 'insight-ic good';
    icEl.textContent = declining > improving ? '⚠' : '✓';
    insEl.innerHTML = `Period-over-period: <b>${improving}</b> metrics improving · <b>${declining}</b> declining. `
      + (p2.ctr > p1.ctr ? `CTR ▲ ${delta(p2.ctr, p1.ctr).pct}` : `CTR ▼ ${delta(p2.ctr, p1.ctr).pct}`)
      + ` · CVR ${delta(p2.cvr, p1.cvr).pct}.`;
  }
}
