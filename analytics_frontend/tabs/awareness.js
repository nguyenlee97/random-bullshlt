/**
 * tabs/awareness.js — Awareness tab orchestrator
 * Renders the HTML shell then delegates to component modules:
 *   scorecard.js, a1-reach.js, a2-viewability.js, a3-matrix.js
 */
import { renderScorecard }           from './awareness/scorecard.js';
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
    brand:       r.brand        || r.Brand || campaignId.replace(/-\d+$/, '') || 'Unknown',
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
      <div class="card-usecase">
        <b>When to use:</b> Check if the campaign is expanding reach or repeatedly hitting the same users.
      </div>
      <div class="card-rule">
        <b>Decision rule:</b> Reach% declining + Impressions flat → over-frequency. Frequency &gt;5 → add frequency cap.
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_aw_reach"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_aw_reach">i</span>
        <span id="ins_aw_reach">—</span>
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
      <div class="card-usecase">
        <b>When to use:</b> Monitor buying efficiency — is cost-per-mille trending up or stabilising?
      </div>
      <div class="card-rule">
        <b>Decision rule:</b> CPM rising &gt;15% over benchmark → renegotiate placements or broaden targeting.
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_aw_cpm"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_aw_cpm">i</span>
        <span id="ins_aw_cpm">—</span>
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
      <div class="card-usecase">
        <b>When to use:</b> Understand the spread of daily frequency — are most days healthy or over-exposed?
      </div>
      <div class="card-rule">
        <b>Decision rule:</b> &gt;30% of days in the 5–7 or 7+ band → aggressive frequency cap needed.
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap" style="min-height:200px"><canvas id="ch_aw_freq"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_aw_freq">i</span>
        <span id="ins_aw_freq">—</span>
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
      <div class="card-usecase">
        <b>When to use:</b> Audit each placement's viewability — are ads actually being seen?
      </div>
      <div class="card-rule">
        <b>Decision rule:</b> VI &lt;50% = non-viewable inventory → pause or replace that placement.
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_aw_vi"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_aw_vi">i</span>
        <span id="ins_aw_vi">—</span>
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
      <div class="card-usecase">
        <b>When to use:</b> For video formats — understand where viewers drop off in the creative.
      </div>
      <div class="card-rule">
        <b>Decision rule:</b> &lt;30% complete at Q2 → shorten creative or improve opening hook.
      </div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div id="aw-funnel" style="margin-bottom:12px"></div>
        <div class="chart-wrap" style="min-height:140px; position:relative">
          <canvas id="ch_aw_funnel"></canvas>
        </div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_aw_funnel">i</span>
        <span id="ins_aw_funnel">—</span>
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
      <div class="card-usecase">
        <b>When to use:</b> Side-by-side comparison of all channels on reach efficiency, cost, and viewability.
      </div>
      <div class="card-rule">
        <b>Decision rule:</b> High CPM + low VI = poor ROI placement. Low Freq + high Reach = strong awareness driver to scale.
      </div>
      <div class="card-body auto">
        <div id="aw-matrix"></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_aw_matrix">i</span>
        <span id="ins_aw_matrix">—</span>
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
