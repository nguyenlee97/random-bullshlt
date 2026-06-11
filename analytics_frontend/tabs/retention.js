/**
 * tabs/retention.js — Retention tab orchestrator
 * Renders HTML shell then delegates to:
 *   scorecard.js, d1-reengagement.js, d2-saturation.js
 */
import { renderScorecard }                  from './retention/scorecard.js';
import { drawWoWReach, drawFreqByPlacement } from './retention/d1-reengagement.js';
import { drawCtrDecayCurve, renderSaturationTable } from './retention/d2-saturation.js';

function norm(r) {
  const campaignId  = r.campaignId  || r['Campaign ID'] || '';
  const placementId = r.placementId || r.zone || r.Zone || '';
  return {
    date:        r.date    || '',
    zone:        placementId,
    channel:     r.channel || '',
    campaignId,
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
  <!-- RT Scorecard -->
  <div class="scorecard" id="rt-scorecard"></div>

  <!-- ── D1: Re-engagement & Frequency ────────────────────────── -->
  <div class="section-h"><span class="uc">D1</span> Week-over-Week Reach · Frequency by Placement</div>

  <div class="grid">
    <!-- D1-a: WoW reach + frequency -->
    <div class="card">
      <div class="card-head">
        <span class="badge rt">D1</span>
        <div>
          <h3>Week-over-Week Reach &amp; Frequency</h3>
          <div class="sub">Weekly reach bars · Avg frequency line (right axis)</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Evaluate whether the campaign expands reach to new users weekly or becomes repetitive.</div>
      <div class="card-rule"><b>Decision rule:</b> Flat reach + rising frequency week-on-week → audience exhausted. Broaden targeting or add new placements.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_rt_wow"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_rt_wow">i</span>
        <span id="ins_rt_wow">—</span>
      </div>
    </div>

    <!-- D1-b: Frequency by placement -->
    <div class="card">
      <div class="card-head">
        <span class="badge rt">D1</span>
        <div>
          <h3>Avg Frequency by Placement</h3>
          <div class="sub">🟢 ≤3x healthy · 🟡 3–5x monitor · 🔴 &gt;5x over-exposed</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Identify which placements are over-serving to the same users.</div>
      <div class="card-rule"><b>Decision rule:</b> Frequency &gt;5x on any placement → apply frequency cap immediately to prevent brand fatigue.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_rt_freq_pl"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_rt_freq_pl">i</span>
        <span id="ins_rt_freq_pl">—</span>
      </div>
    </div>
  </div>

  <!-- ── D2: Creative Fatigue & Saturation ─────────────────────── -->
  <div class="section-h"><span class="uc">D2</span> CTR Decay Curve · Audience Saturation Analysis</div>

  <!-- D2-a: CTR decay curve -->
  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge rt">D2</span>
        <div>
          <h3>CTR Decay Curve — Creative Fatigue Monitor</h3>
          <div class="sub">Daily CTR · 7-day rolling avg · Launch baseline (dashed)</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Detect creative fatigue by tracking whether CTR trends below the campaign's opening baseline.</div>
      <div class="card-rule"><b>Decision rule:</b> Rolling avg &gt;15% below baseline → creative refresh needed. &gt;25% → immediate action.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_rt_decay"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_rt_decay">i</span>
        <span id="ins_rt_decay">—</span>
      </div>
    </div>
  </div>

  <!-- D2-b: Saturation table -->
  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge rt">D2</span>
        <div>
          <h3>Audience Saturation Analysis — Placement Scorecard</h3>
          <div class="sub">Composite saturation score (0–100) from Frequency + CTR Decay + Viewability</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Rank placements by saturation risk to prioritise where to pause, refresh, or scale.</div>
      <div class="card-rule"><b>Decision rule:</b> Score ≥70 → pause or rotate creative. Score 40–70 → monitor weekly. Score &lt;40 → safe to scale.</div>
      <div class="card-body auto">
        <div id="rt-saturation"></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_rt_sat">i</span>
        <span id="ins_rt_sat">—</span>
      </div>
    </div>
  </div>
  `;
}

export function render(State, utils) {
  const panel = document.getElementById('p-rt');
  if (!panel) return;

  const src = (State.filtered.length > 0 || hasActiveFilter(State.filters))
    ? State.filtered
    : State.allData;

  const rows = src.map(norm);
  panel.innerHTML = buildShell();

  renderScorecard(rows, utils);
  drawWoWReach(rows, utils);
  drawFreqByPlacement(rows, utils);
  drawCtrDecayCurve(rows, utils);
  renderSaturationTable(rows, utils);
}
