/**
 * tabs/awareness.js — Awareness tab orchestrator
 * Renders the HTML shell then delegates to component modules:
 *   scorecard.js, a1-reach.js, a2-viewability.js, a3-matrix.js
 */
import { renderScorecard }           from './awareness/scorecard.js?v=1.1.4';
import { drawReachTrend, drawCpmTrend, drawFreqDistribution } from './awareness/a1-reach.js';
import { drawViewabilityByPlacement, drawVideoFunnel }        from './awareness/a2-viewability.js';
import { renderMatrix }              from './awareness/a3-matrix.js';

/* ── normalise raw backend row (same logic as daily-ops) ─────────── */
function norm(r) {
  const campaignId  = r.campaignId  || r['Campaign ID'] || '';
  const placementId = r.placementId || r.zone || r.Zone || '';
  const channel     = r.channel || '';
  return {
    date:        r.date         || '',
    brand:       r.brand        || r.Brand || campaignId || 'Unknown',
    zone:        placementId,
    channel,
    campaignId,
    audience:    r.audienceSegment || r['Audience Segment'] || channel || 'Unknown',
    format:      r.format || '',
    impressions: Number(r.impressions || 0),
    reach:       Number(r.reach       || 0),
    clicks:      Number(r.clicks      || 0),
    ctr:         Number(r.ctr         || 0),
    spend:       Number(r.spend       || r.spendVnd || r['Spend VND'] || 0),
    cpm:         Number(r.cpm         || 0),
    conversions: Number(r.conversions || 0),
    vi:          Number(r.vi          || 0),
    cvr:         Number(r.cvr         || 0),
    roas:        Number(r.roas        || 0),
  };
}

function hasActiveFilter(f) {
  return f.brand || f.zone || f.audience || f.startDate || f.endDate;
}

/* ── HTML skeleton ───────────────────────────────────────────────── */
function buildShell() {
  return `
  <!-- AW Scorecard -->
  <div class="scorecard" id="aw-scorecard"></div>

  <!-- ── A1: Reach & Frequency ─────────────────────────────────── -->
  <div class="section-h">
    <span class="uc">A1</span>
    Daily Reach Trend · Frequency Distribution · CPM Efficiency
  </div>

  <div class="grid">

    <!-- A1-a: Reach + Frequency combo -->
    <div class="card">
      <div class="card-head">
        <span class="badge aw">A1</span>
        <div>
          <h3>Daily Reach &amp; Frequency Trend</h3>
          <div class="sub">Reach bars · Frequency line (right axis)</div>
        </div>
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_aw_reach"></canvas></div>
      </div>
    </div>

    <!-- A1-b: CPM Trend -->
    <div class="card">
      <div class="card-head">
        <span class="badge aw">A1</span>
        <div>
          <h3>CPM Trend &amp; Period Benchmark</h3>
          <div class="sub">Daily avg CPM vs period average (dashed)</div>
        </div>
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_aw_cpm"></canvas></div>
      </div>
    </div>

  </div><!-- /grid A1-a + A1-b -->

  <!-- A1-c: Frequency distribution -->
  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge aw">A1</span>
        <div>
          <h3>Frequency Distribution (Daily Bands)</h3>
          <div class="sub">Count of days falling in each frequency band</div>
        </div>
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap" style="min-height:200px"><canvas id="ch_aw_freq"></canvas></div>
      </div>
    </div>
  </div>

  <!-- ── A2: Viewability ───────────────────────────────────────── -->
  <div class="section-h">
    <span class="uc">A2</span>
    Viewability by Placement · Video Completion Funnel
  </div>

  <div class="grid">

    <!-- A2-a: Viewability horizontal bar -->
    <div class="card">
      <div class="card-head">
        <span class="badge aw">A2</span>
        <div>
          <h3>Viewability by Placement</h3>
          <div class="sub">Weighted-avg VI% · 🟢 ≥70 · 🟡 50–70 · 🔴 &lt;50</div>
        </div>
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_aw_vi"></canvas></div>
      </div>
    </div>

    <!-- A2-b: Video completion funnel + doughnut -->
    <div class="card">
      <div class="card-head">
        <span class="badge aw">A2</span>
        <div>
          <h3>Video Completion Funnel</h3>
          <div class="sub">Impression → Q1 → Q2 → Complete (VI-derived estimate)</div>
        </div>
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div id="aw-funnel" style="margin-bottom:12px"></div>
        <div class="chart-wrap" style="min-height:140px; position:relative">
          <canvas id="ch_aw_funnel"></canvas>
        </div>
      </div>
    </div>

  </div><!-- /grid A2 -->

  <!-- ── A3: Channel Performance Matrix ───────────────────────── -->
  <div class="section-h">
    <span class="uc">A3</span>
    Channel Performance Matrix — Reach · Frequency · CPM · Viewability
  </div>

  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge aw">A3</span>
        <div>
          <h3>Channel Performance Matrix</h3>
          <div class="sub">All awareness KPIs by channel — sortable at a glance</div>
        </div>
      </div>
      <div class="card-body auto">
        <div id="aw-matrix"></div>
      </div>
    </div>
  </div>
  `;
}

/* ── Main render ─────────────────────────────────────────────────── */
export function render(State, utils) {
  const panel = document.getElementById('p-aw');
  if (!panel) return;

  const src = (State.filtered.length > 0 || hasActiveFilter(State.filters))
    ? State.filtered
    : State.allData;

  const rows = src.map(norm);

  // Inject shell HTML
  panel.innerHTML = buildShell();

  // Delegate to components
  renderScorecard(rows, utils);
  drawReachTrend(rows, utils);
  drawCpmTrend(rows, utils);
  drawFreqDistribution(rows, utils);
  drawViewabilityByPlacement(rows, utils);
  drawVideoFunnel(rows, utils);
  renderMatrix(rows, utils);
}
