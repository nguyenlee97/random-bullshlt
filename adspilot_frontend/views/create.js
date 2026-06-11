/**
 * views/create.js — Create/Edit Campaign form (shell, sync, submit)
 * Depends on: create_zones.js, create_targeting.js, create_dmp.js
 */

function blankForm() {
  const today = new Date().toISOString().slice(0, 10);
  const next  = new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10);
  return {
    brand: '', advertiser: '', objective: 'awareness',
    status: 'pending', budget: 100_000_000, daily: 10_000_000,
    rate: 35_000, rateType: 'CPM',
    startDate: today, endDate: next,
    creative: { name: '', size: '720x1280', url: '' },
    placements: [],
    targeting: { geo: [], age: [], gender: [], deviceOS: [], deviceBrand: [],
                 marital: [], parental: [], education: [], income: [], career: [],
                 interest: [], weather: [] },
    dmp: { include: [], exclude: [] },
  };
}

async function renderCreate(payload) {
  showLoading();
  if (!editing && !formState) formState = blankForm();

  // Load all catalogs in parallel
  const [zones, targeting, dmpItems] = await Promise.all([
    loadZones(), loadTargeting(), loadDmp()
  ]);

  const isEdit = !!editing;
  const f = formState;

  function sel(val, opt) { return val === opt ? 'selected' : ''; }
  function opt(v, label, cur) { return `<option value="${v}" ${sel(cur, v)}>${label || v}</option>`; }

  // Zone section HTML (from create_zones.js)
  const zonesHTML = buildZonesSection(zones, f);
  // Demographics HTML (from create_targeting.js)
  const tgtHTML = buildTargetingSection(targeting, f);
  // DMP HTML (from create_dmp.js)
  const dmpHTML = buildDmpSection(dmpItems, f);

  setMain(`
    <div class="crumb">
      <a onclick="navTo('orders')">All Orders</a>
      <span class="sep">›</span>
      <b>${isEdit ? 'Edit Order ' + editing : 'Create New Order'}</b>
    </div>

    <div id="audiBar"></div>

    <!-- BANNER / ORDER INFO -->
    <div class="card">
      <div class="head">📦 Banner / Order Info
        <span style="margin-left:auto;display:flex;align-items:center;gap:8px">
          <span style="font-size:11.5px;color:var(--muted)">Status:</span>
          <span class="pill-status ${f.status}">${f.status}</span>
          ${isEdit ? `<span style="font-size:11px;color:var(--muted)">ID: ${editing}</span>` : ''}
        </span>
      </div>
      <div class="body">
        <div class="section-title">Source</div>
        <div class="row">
          <div class="lab">Source</div>
          <div><select id="f_src" class="ipt sm"><option>CRM</option><option>Self-serve</option><option>Programmatic</option></select></div>
        </div>

        <div class="section-title" style="margin-top:14px">Banner Ads</div>
        <div class="row">
          <div class="lab">Name <span class="req">*</span></div>
          <div><input class="ipt md" id="f_creativeName" value="${escHTML(f.creative.name)}" placeholder="e.g. BrandX Summer Launch 6/2026"></div>
        </div>
        <div class="row">
          <div class="lab">Brand <span class="req">*</span></div>
          <div><input class="ipt md" id="f_brand" value="${escHTML(f.brand)}" placeholder="Brand name"></div>
        </div>
        <div class="row">
          <div class="lab">Advertiser</div>
          <div><input class="ipt md" id="f_adv" value="${escHTML(f.advertiser)}" placeholder="Agency / Company"></div>
        </div>
        <div class="row">
          <div class="lab">Objective</div>
          <div>
            <select id="f_obj" class="ipt sm">
              ${opt('awareness','Awareness',f.objective)}
              ${opt('consideration','Consideration',f.objective)}
              ${opt('conversion','Conversion',f.objective)}
              ${opt('retention','Retention',f.objective)}
            </select>
          </div>
        </div>
        <div class="row">
          <div class="lab">Size</div>
          <div><input class="ipt sm" id="f_size" value="${escHTML(f.creative.size)}" placeholder="720x1280"></div>
        </div>
        <div class="row">
          <div class="lab">Banner File URL</div>
          <div><input class="ipt md" id="f_url" value="${escHTML(f.creative.url)}" placeholder="https://cdn.adspilot.vn/..."></div>
        </div>
        <div class="row">
          <div class="lab">Target URL</div>
          <div><input class="ipt md" id="f_targetUrl" value="${escHTML(f.targetUrl || '')}" placeholder="https://landing.brand.com/..."></div>
        </div>
        <div class="row">
          <div class="lab">Volume toggle</div>
          <div><label class="check"><input type="checkbox" ${f.allowVolume ? 'checked' : ''}> Enable</label></div>
        </div>
        <div class="row">
          <div class="lab">Click Tag</div>
          <div><label class="check"><input type="checkbox" checked> Enable</label></div>
        </div>
      </div>
    </div>

    <!-- TRACKING -->
    <div class="card">
      <div class="head">📍 Tracking UTM Source</div>
      <div class="body">
        <div class="row">
          <div class="lab">UTM Tracking</div>
          <div><label class="check"><input type="checkbox"> Enable</label></div>
        </div>
      </div>
    </div>

    <!-- THIRD PARTY -->
    <div class="card">
      <div class="head">🧷 Third Party Tracking</div>
      <div class="body">
        <div class="row">
          <div class="lab">Impression URL</div>
          <div><input class="ipt md" placeholder="https://3p.tracker/imp?..."></div>
        </div>
        <div class="row">
          <div class="lab">Click URL</div>
          <div><input class="ipt md" placeholder="https://3p.tracker/click?..."></div>
        </div>
        <div class="row">
          <div class="lab">Video events</div>
          <div>
            <label class="check"><input type="checkbox" checked> Creative View</label>
            <label class="check"><input type="checkbox" checked> First quartile</label>
            <label class="check"><input type="checkbox" checked> Mid point</label>
            <label class="check"><input type="checkbox" checked> Third quartile</label>
            <label class="check"><input type="checkbox" checked> Fullview</label>
            <label class="check"><input type="checkbox"> Progress 30s</label>
          </div>
        </div>
      </div>
    </div>

    <!-- PRICE INFO -->
    <div class="card">
      <div class="head">💰 Price Information</div>
      <div class="body">
        <div class="row">
          <div class="lab">Rate <span class="req">*</span></div>
          <div>
            <input class="ipt sm" type="number" id="f_rate" value="${f.rate}" style="display:inline-block;width:120px">
            <select id="f_rateType" class="ipt sm" style="display:inline-block;width:90px">
              ${opt('CPM','CPM',f.rateType)}${opt('CPC','CPC',f.rateType)}${opt('CPV','CPV',f.rateType)}${opt('FlatFee','FlatFee',f.rateType)}
            </select>
          </div>
        </div>
        <div class="row">
          <div class="lab">Lifetime limit <span class="req">*</span></div>
          <div>
            <input class="ipt sm" type="number" id="f_budget" value="${f.budget}" style="width:160px">
            <span style="color:var(--muted);font-size:11px;margin-left:6px">đ</span>
          </div>
        </div>
        <div class="row">
          <div class="lab">Daily limit <span class="req">*</span></div>
          <div>
            <input class="ipt sm" type="number" id="f_daily" value="${f.daily}" style="width:120px">
            <select class="ipt sm" style="display:inline-block;width:120px;margin-left:6px">
              <option>impression</option><option>budget (đ)</option>
            </select>
          </div>
        </div>
        <div class="row">
          <div class="lab">Date range</div>
          <div>
            <input class="ipt sm" type="date" id="f_start" value="${f.startDate}" style="width:145px">
            <span style="color:var(--muted);margin:0 6px">→</span>
            <input class="ipt sm" type="date" id="f_end"   value="${f.endDate}"   style="width:145px">
          </div>
        </div>
        <div class="row">
          <div class="lab">Frequency Cap</div>
          <div><input class="ipt sm" id="f_freqCap" value="${escHTML(f.freqCap || '3 imp / user / day')}" style="width:200px"></div>
        </div>
      </div>
    </div>

    <!-- TARGETING -->
    <div class="card">
      <div class="head">🎯 Targeting</div>
      <div class="body">
        ${zonesHTML}
        ${tgtHTML}
        ${dmpHTML}
      </div>
      <div class="actions">
        <button class="btn" id="btnActivate" onclick="submitForm('${isEdit ? 'update' : 'create'}','active')">
          ${isEdit ? '💾 Update & Activate' : '＋ Create & Activate'}
        </button>
        <button class="btn navy" onclick="submitForm('${isEdit ? 'update' : 'create'}','pending')">Save as Pending</button>
        <button class="btn sec"  onclick="submitForm('${isEdit ? 'update' : 'create'}','draft')">Save Draft</button>
        <button class="btn sec"  onclick="cancelForm()">Cancel</button>
        <span style="margin-left:auto;font-size:11px;color:var(--muted)">
          API: <code>${isEdit ? 'PUT /api/orders/' + editing : 'POST /api/orders'}</code>
        </span>
      </div>
    </div>
  `);

  // Bind all text/select inputs → syncForm
  ['f_brand','f_adv','f_obj','f_creativeName','f_size','f_url','f_targetUrl',
   'f_rate','f_rateType','f_budget','f_daily','f_start','f_end'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input',  syncForm);
    el.addEventListener('change', syncForm);
  });

  refreshAudienceBar();
}

/* ── Form sync ───────────────────────────────────────────────────────────────── */
function syncForm() {
  if (!formState) return;
  const g = id => { const e = document.getElementById(id); return e ? e.value : ''; };
  formState.brand            = g('f_brand');
  formState.advertiser       = g('f_adv');
  formState.objective        = g('f_obj');
  formState.creative.name    = g('f_creativeName');
  formState.creative.size    = g('f_size');
  formState.creative.url     = g('f_url');
  formState.targetUrl        = g('f_targetUrl');
  formState.rate             = +g('f_rate')   || 0;
  formState.rateType         = g('f_rateType');
  formState.budget           = +g('f_budget') || 0;
  formState.daily            = +g('f_daily')  || 0;
  formState.startDate        = g('f_start');
  formState.endDate          = g('f_end');
  formState.freqCap          = g('f_freqCap');
  refreshAudienceBar();
}

/* ── Submit ──────────────────────────────────────────────────────────────────── */
async function submitForm(action, status) {
  syncForm();
  if (!formState.brand)         { toast('⚠ Brand is required', true); return; }
  if (!formState.creative.name) { toast('⚠ Creative name is required', true); return; }

  formState.status = status;
  const btn = document.getElementById('btnActivate');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }

  try {
    let result;
    if (action === 'create') {
      result = await Api.createOrder(formState);
      toast('✓ Created ' + result.id);
      // Show warnings if any
      if (result.warnings && result.warnings.length) {
        setTimeout(() => toast('⚠ ' + result.warnings.length + ' zone warning(s) — check API Docs'), 2500);
      }
    } else {
      result = await Api.updateOrder(editing, formState);
      toast('✓ Updated ' + editing);
    }
    editing   = null;
    formState = null;
    navTo('orders');
  } catch (e) {
    toast('Error: ' + e.message, true);
    if (btn) { btn.disabled = false; btn.textContent = action === 'create' ? '＋ Create & Activate' : '💾 Update & Activate'; }
  }
}

function cancelForm() {
  editing   = null;
  formState = null;
  navTo('orders');
}
