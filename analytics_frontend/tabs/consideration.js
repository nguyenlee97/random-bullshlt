/**
 * tabs/consideration.js — Consideration tab orchestrator
 * Renders the full HTML shell then delegates to component modules:
 *   scorecard.js, b1-ctr.js, b2-clicks.js, b3-engagement.js
 */
import { renderScorecard }             from './consideration/scorecard.js';
import { drawCtrTrend, drawCtrVsCpmScatter } from './consideration/b1-ctr.js';
import { drawClickVolume, renderTopClicksTable } from './consideration/b2-clicks.js';
import { drawCtrByFormat, renderCampaignRanking } from './consideration/b3-engagement.js';

function norm(r) {
  const campaignId  = r.campaignId  || r['Campaign ID'] || '';
  const placementId = r.placementId || r.zone || r.Zone || '';
  const channel     = r.channel || '';
  return {
    date:        r.date         || '',
    zone:        placementId,
    channel,
    campaignId,
    format:      r.format || 'banner',
    impressions: Number(r.impressions || 0),
    reach:       Number(r.reach       || 0),
    clicks:      Number(r.clicks      || 0),
    ctr:         Number(r.ctr         || 0),
    spend:       Number(r.spend       || r.spendVnd || r['Spend VND'] || 0),
    cpm:         Number(r.cpm         || 0),
    conversions: Number(r.conversions || 0),
    vi:          Number(r.vi          || 0),
  };
}

function hasActiveFilter(f) {
  return f.brand || f.zone || f.audience || f.startDate || f.endDate;
}

function buildShell() {
  return `
  <!-- CO Scorecard -->
  <div class="scorecard" id="co-scorecard"></div>

  <!-- ── B1: CTR Performance ───────────────────────────────────── -->
  <div class="section-h"><span class="uc">B1</span> CTR Trend by Placement · CTR vs CPM Efficiency</div>

  <div class="grid">

    <!-- B1-a: CTR trend multi-line -->
    <div class="card">
      <div class="card-head">
        <span class="badge co">B1</span>
        <div>
          <h3>CTR Trend — Top 5 Placements</h3>
          <div class="sub">Daily CTR % per placement over time</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Track engagement momentum per placement — is CTR holding, rising, or dropping?</div>
      <div class="card-rule"><b>Decision rule:</b> CTR declining &gt;20% vs first week → creative fatigue on that placement. Pause or swap.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_co_ctr_trend"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_co_ctr_trend">i</span>
        <span id="ins_co_ctr_trend">—</span>
      </div>
    </div>

    <!-- B1-b: CTR vs CPM scatter -->
    <div class="card">
      <div class="card-head">
        <span class="badge co">B1</span>
        <div>
          <h3>CTR vs CPM — Efficiency Scatter</h3>
          <div class="sub">Bubble size = impression volume · colour = channel</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Find placements delivering high CTR at low cost (upper-left quadrant = winners).</div>
      <div class="card-rule"><b>Decision rule:</b> Lower-right quadrant = high CPM + low CTR → renegotiate rates or cut placement.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_co_scatter"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_co_scatter">i</span>
        <span id="ins_co_scatter">—</span>
      </div>
    </div>

  </div>

  <!-- ── B2: Click Volume ───────────────────────────────────────── -->
  <div class="section-h"><span class="uc">B2</span> Daily Click Volume · Top Placements by Clicks</div>

  <!-- B2-a: Stacked click bar -->
  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge co">B2</span>
        <div>
          <h3>Daily Click Volume by Channel</h3>
          <div class="sub">Stacked bars — total daily clicks segmented by channel</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Monitor day-to-day click delivery — identify spikes, dips, and channel contribution.</div>
      <div class="card-rule"><b>Decision rule:</b> Single channel dominating &gt;80% → diversification risk. Day-over-day drop &gt;30% → investigate delivery issue.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap tall"><canvas id="ch_co_clicks"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_co_clicks">i</span>
        <span id="ins_co_clicks">—</span>
      </div>
    </div>
  </div>

  <!-- B2-b: Top placements table -->
  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge co">B2</span>
        <div>
          <h3>Top Placements by Click Volume</h3>
          <div class="sub">Ranked by total clicks · includes CTR, CPC, Conversions</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Find the highest-traffic placements to prioritise for budget allocation.</div>
      <div class="card-rule"><b>Decision rule:</b> High clicks + low CTR → large impression base. High CPC + low conv → low-intent traffic.</div>
      <div class="card-body auto">
        <div id="co-top-clicks"></div>
      </div>
    </div>
  </div>

  <!-- ── B3: Engagement Breakdown ──────────────────────────────── -->
  <div class="section-h"><span class="uc">B3</span> CTR by Channel × Format · Campaign Engagement Ranking</div>

  <!-- B3-a: Grouped bar channel x format -->
  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge co">B3</span>
        <div>
          <h3>CTR by Channel &amp; Format</h3>
          <div class="sub">Grouped bars — find the highest-engaging channel × format combination</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Determine which ad format (banner vs video) performs best on each channel.</div>
      <div class="card-rule"><b>Decision rule:</b> Video CTR &gt;2× banner CTR on same channel → shift budget to video for awareness uplift.</div>
      <div class="card-body auto" style="padding-bottom:16px">
        <div class="chart-wrap" style="min-height:240px"><canvas id="ch_co_ctr_fmt"></canvas></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_co_ctr_fmt">i</span>
        <span id="ins_co_ctr_fmt">—</span>
      </div>
    </div>
  </div>

  <!-- B3-b: Campaign ranking table -->
  <div class="grid wide">
    <div class="card">
      <div class="card-head">
        <span class="badge co">B3</span>
        <div>
          <h3>Campaign Engagement Ranking</h3>
          <div class="sub">All campaigns ranked by CTR — with clicks, spend, CPC and CVR</div>
        </div>
      </div>
      <div class="card-usecase"><b>When to use:</b> Holistic view of every campaign's engagement efficiency in one table.</div>
      <div class="card-rule"><b>Decision rule:</b> Top-CTR campaign with low CVR = engagement without conversion → fix landing page or offer.</div>
      <div class="card-body auto">
        <div id="co-camp-ranking"></div>
      </div>
      <div class="card-insight">
        <span class="insight-ic" id="ic_co_ranking">i</span>
        <span id="ins_co_ranking">—</span>
      </div>
    </div>
  </div>
  `;
}

export function render(State, utils) {
  const panel = document.getElementById('p-co');
  if (!panel) return;

  const src = (State.filtered.length > 0 || hasActiveFilter(State.filters))
    ? State.filtered
    : State.allData;

  const rows = src.map(norm);

  panel.innerHTML = buildShell();

  renderScorecard(rows, utils);
  drawCtrTrend(rows, utils);
  drawCtrVsCpmScatter(rows, utils);
  drawClickVolume(rows, utils);
  renderTopClicksTable(rows, utils);
  drawCtrByFormat(rows, utils);
  renderCampaignRanking(rows, utils);
}
