/**
 * tabs/conversion.js — Conversion tab orchestrator
 * Renders HTML shell then delegates to:
 *   scorecard.js, c1-conv-trend.js, c2-cost.js, c3-funnel.js
 */
import { renderScorecard }                   from './conversion/scorecard.js';
import { drawConversionTrend, drawCvrByChannel } from './conversion/c1-conv-trend.js';
import { drawCpaByPlacement, drawSpendVsConvScatter } from './conversion/c2-cost.js';
import { drawConversionFunnel, renderTopConversionsTable } from './conversion/c3-funnel.js';

function norm(r) {
  const campaignId  = r.campaignId  || r['Campaign ID'] || '';
  const placementId = r.placementId || r.zone || r.Zone || '';
  return {
    date:        r.date    || '',
    zone:        placementId,
    channel:     r.channel || '',
    campaignId,
    format:      r.format  || 'banner',
    impressions: Number(r.impressions || 0),
    reach:       Number(r.reach       || 0),
    clicks:      Number(r.clicks      || 0),
    conversions: Number(r.conversions || 0),
    spend:       Number(r.spend || r.spendVnd || r['Spend VND'] || 0),
    cpm:         Number(r.cpm   || 0),
    vi:          Number(r.vi    || 0),
  };
}

function hasActiveFilter(f) {
  return f.brand || f.zone || f.audience || f.startDate || f.endDate;
}

function buildShell() {
  return `
  <!-- CV Scorecard -->
  <div class="scorecard" id="cv-scorecard"></div>

  <!-- ── C1: Conversion Trend ─────────────────────────────────── -->
  <div class="section-h"><span class="uc">C1</span> Daily Conversion Trend · CVR by Channel</div>

  <div class="grid">
    <!-- C1-a: Conversions + CVR combo -->
    <div class="card">
      <div class="card-head">
        <span class="badge cv">C1</span>
        <div>
          <h3>Daily Conversions &amp; CVR Trend</h3>
          <div class="sub">Conversion bars · CVR % line (right axis)</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Track conversion delivery day-by-day and whether click-to-conversion rate is improving.</div>
      <div class="card-rule"><b>Decision rule:</b> Clicks rising but CVR falling → landing page or offer issue, not a media problem.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_cv_trend"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_cv_trend">i</span>
        <span id="ins_cv_trend">—</span>
      </div>
    </div>

    <!-- C1-b: CVR by channel -->
    <div class="card">
      <div class="card-head">
        <span class="badge cv">C1</span>
        <div>
          <h3>CVR by Channel</h3>
          <div class="sub">Click-to-conversion rate per channel · 🟢 ≥5% · 🟡 2–5% · 🔴 &lt;2%</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Find which channel's audience converts best after clicking — signals audience quality.</div>
      <div class="card-rule"><b>Decision rule:</b> Channel with high CVR + high CPC → still worth it if CPA is acceptable.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap" style="min-height:220px"><canvas id="ch_cv_cvr_ch"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_cv_cvr_ch">i</span>
        <span id="ins_cv_cvr_ch">—</span>
      </div>
    </div>
  </div>

  <!-- ── C2: Cost Efficiency ───────────────────────────────────── -->
  <div class="section-h"><span class="uc">C2</span> CPA by Placement · Spend vs Conversions</div>

  <div class="grid">
    <!-- C2-a: CPA horizontal bar -->
    <div class="card">
      <div class="card-head">
        <span class="badge cv">C2</span>
        <div>
          <h3>Cost per Conversion (CPA) by Placement</h3>
          <div class="sub">Sorted ascending — cheapest conversions first</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Identify the most cost-efficient placements for driving conversions.</div>
      <div class="card-rule"><b>Decision rule:</b> CPA &gt;2× median → deprioritise. Shift budget to green placements.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_cv_cpa"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_cv_cpa">i</span>
        <span id="ins_cv_cpa">—</span>
      </div>
    </div>

    <!-- C2-b: Spend vs Conversions scatter -->
    <div class="card">
      <div class="card-head">
        <span class="badge cv">C2</span>
        <div>
          <h3>Spend vs Conversions — Campaign Scatter</h3>
          <div class="sub">Bubble size = click volume · upper-left = best efficiency</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> See which campaigns deliver conversions proportional to their spend.</div>
      <div class="card-rule"><b>Decision rule:</b> High spend + low conversions (lower-right) → review offer, creative, or targeting.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_cv_scatter"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_cv_scatter">i</span>
        <span id="ins_cv_scatter">—</span>
      </div>
    </div>
  </div>

  <!-- ── C3: Funnel & Rankings ─────────────────────────────────── -->
  <div class="section-h"><span class="uc">C3</span> Conversion Funnel · Top Converting Campaigns</div>

  <!-- C3-a: Funnel + gauge -->
  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge cv">C3</span>
        <div>
          <h3>End-to-End Conversion Funnel</h3>
          <div class="sub">Impressions → Reach → Clicks → Conversions with drop-off rates</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Diagnose where the biggest drop-off occurs and prioritise optimisation efforts.</div>
      <div class="card-rule"><b>Decision rule:</b> Large drop at click stage → fix CTR (creative). Large drop at conversion → fix landing page.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div style="display:grid;grid-template-columns:1fr 160px;gap:20px;align-items:center">
          <div id="cv-funnel"></div>
          <div style="position:relative;height:160px">
            <canvas id="ch_cv_gauge"></canvas>
            <div id="cv-gauge-label" style="
              position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
              font-size:22px;font-weight:800;color:var(--navy);text-align:center;
              pointer-events:none;line-height:1.2">—</div>
            <div style="text-align:center;font-size:10px;color:var(--muted);margin-top:4px">CVR</div>
          </div>
        </div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_cv_funnel">i</span>
        <span id="ins_cv_funnel">—</span>
      </div>
    </div>
  </div>

  <!-- C3-b: Top converting campaigns table -->
  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge cv">C3</span>
        <div>
          <h3>Top Converting Campaigns</h3>
          <div class="sub">Ranked by total conversions · CVR pills · CPA</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Holistic conversion performance view — rank and compare all campaigns.</div>
      <div class="card-rule"><b>Decision rule:</b> Top-conv campaign with highest CPA → scale budget only after verifying LTV supports CPA.</div>
      <div class="card-body auto">
        <div id="cv-top-conv"></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_cv_top">i</span>
        <span id="ins_cv_top">—</span>
      </div>
    </div>
  </div>
  `;
}

export function render(State, utils) {
  const panel = document.getElementById('p-cv');
  if (!panel) return;

  const src = (State.filtered.length > 0 || hasActiveFilter(State.filters))
    ? State.filtered
    : State.allData;

  const rows = src.map(norm);
  panel.innerHTML = buildShell();

  renderScorecard(rows, utils);
  drawConversionTrend(rows, utils);
  drawCvrByChannel(rows, utils);
  drawCpaByPlacement(rows, utils);
  drawSpendVsConvScatter(rows, utils);
  drawConversionFunnel(rows, utils);
  renderTopConversionsTable(rows, utils);
}
