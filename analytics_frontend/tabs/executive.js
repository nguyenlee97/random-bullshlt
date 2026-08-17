/**
 * tabs/executive.js — Executive tab orchestrator
 * Renders HTML shell then delegates to:
 *   scorecard.js, e1-health.js, e2-budget.js, e3-kpi.js
 */
import { renderScorecard }                    from './executive/scorecard.js?v=1.1.4';
import { renderHealthTable, drawRadarChart }  from './executive/e1-health.js';
import { drawSpendPacing, drawChannelAllocation } from './executive/e2-budget.js';
import { renderPoPTable }                     from './executive/e3-kpi.js?v=1.1.4';

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
  <!-- EX Scorecard (9-wide grid) -->
  <div id="ex-scorecard" style="margin-bottom:20px"></div>

  <!-- ── E1: Campaign Health ───────────────────────────────────── -->
  <div class="section-h"><span class="uc">E1</span> Campaign Health — Traffic Light Scoring &amp; Radar</div>

  <div class="grid">
    <!-- E1-a: Health table (takes 2 cols) -->
    <div class="card" style="grid-column:1/-1">
      <div class="card-head">
        <span class="badge ex">E1</span>
        <div>
          <h3>Campaign Health Scorecard</h3>
          <div class="sub">Composite health score (0–100) across CTR · CVR · VI · Frequency · Spend Efficiency</div>
        </div>
      </div>
      <div class="card-body auto">
        <div id="ex-health-table"></div>
      </div>
    </div>
  </div>

  <!-- E1-b: Radar chart -->
  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge ex">E1</span>
        <div>
          <h3>Top 3 Campaigns — Performance Radar</h3>
          <div class="sub">5-dimension radar: CTR · CVR · Viewability · Frequency Score · Efficiency</div>
        </div>
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap" style="min-height:320px"><canvas id="ch_ex_radar"></canvas></div>
      </div>
    </div>
  </div>

  <!-- ── E2: Budget ────────────────────────────────────────────── -->
  <div class="section-h"><span class="uc">E2</span> Spend Pacing · Channel Budget Allocation</div>

  <div class="grid">
    <!-- E2-a: Pacing line -->
    <div class="card">
      <div class="card-head">
        <span class="badge ex">E2</span>
        <div>
          <h3>Cumulative Spend Pacing</h3>
          <div class="sub">Actual vs ideal linear pacing over campaign period</div>
        </div>
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_ex_pacing"></canvas></div>
      </div>
    </div>

    <!-- E2-b: Donut -->
    <div class="card">
      <div class="card-head">
        <span class="badge ex">E2</span>
        <div>
          <h3>Budget Allocation by Channel</h3>
          <div class="sub">Spend share % per channel — donut view</div>
        </div>
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_ex_donut"></canvas></div>
      </div>
    </div>
  </div>

  <!-- ── E3: Period-over-Period ────────────────────────────────── -->
  <div class="section-h"><span class="uc">E3</span> Period-over-Period KPI Comparison</div>

  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge ex">E3</span>
        <div>
          <h3>KPI Trend — First Half vs Second Half</h3>
          <div class="sub">11 metrics compared across two equal date periods with Δ change signals</div>
        </div>
      </div>
      <div class="card-body auto">
        <div id="ex-pop-table"></div>
      </div>
    </div>
  </div>
  `;
}

export function render(State, utils) {
  const panel = document.getElementById('p-ex');
  if (!panel) return;

  const src = (State.filtered.length > 0 || hasActiveFilter(State.filters))
    ? State.filtered
    : State.allData;

  const rows = src.map(norm);
  panel.innerHTML = buildShell();

  renderScorecard(rows, utils);
  const campaigns = renderHealthTable(rows, utils);
  drawRadarChart(campaigns, utils);
  drawSpendPacing(rows, utils);
  drawChannelAllocation(rows, utils);
  renderPoPTable(rows, utils);
}
