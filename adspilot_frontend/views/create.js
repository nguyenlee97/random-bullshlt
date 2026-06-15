/**
 * views/create.js — Create/Edit Campaign form (shell, sync, submit)
 * Depends on: create_zones.js, create_targeting.js, create_dmp.js
 */

function blankForm() {
  const today = new Date().toISOString().slice(0, 10);
  const next = new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10);
  return {
    brand: '', advertiser: '', objective: 'awareness',
    status: 'pending', budget: 100_000_000, daily: 10_000_000,
    rate: 35_000, rateType: 'CPM',
    startDate: today, endDate: next,
    creative: { name: '', size: '', url: '' },
    creatives: [],         // serialized on submit from creativeGroups
    creativeGroups: [],    // live group-card state [{groupId,zones[],size,format,url,label}]
    placements: [],
    targeting: {
      geo: [], age: [], gender: [], deviceOS: [], deviceBrand: [],
      marital: [], parental: [], education: [], income: [], career: [],
      interest: [], weather: []
    },
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

    <!-- STICKY FORM TAB BAR for direct section navigation -->
    <div class="form-tabs" id="formTabs">
      <button class="form-tab on" data-section="info"      onclick="scrollToSection('info')">📦 Info</button>
      <button class="form-tab"    data-section="zones"     onclick="scrollToSection('zones')">📍 Zones</button>
      <button class="form-tab"    data-section="targeting" onclick="scrollToSection('targeting')">🎯 Targeting</button>
      <button class="form-tab"    data-section="dmp"       onclick="scrollToSection('dmp')">🧩 DMP</button>
      <button class="form-tab"    data-section="creatives" onclick="scrollToSection('creatives')">🎨 Creatives</button>
    </div>

    <div id="audiBar"></div>

    <!-- BANNER / ORDER INFO -->
    <div class="card" id="section-info">
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

        <div class="section-title" style="margin-top:14px">🎨 Creatives</div>
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
              ${opt('awareness', 'Awareness', f.objective)}
              ${opt('consideration', 'Consideration', f.objective)}
              ${opt('conversion', 'Conversion', f.objective)}
              ${opt('retention', 'Retention', f.objective)}
            </select>
          </div>
        </div>
        <!-- Creatives panel is rendered below the zone picker and updated dynamically -->

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
              ${opt('CPM', 'CPM', f.rateType)}${opt('CPC', 'CPC', f.rateType)}${opt('CPV', 'CPV', f.rateType)}${opt('FlatFee', 'FlatFee', f.rateType)}
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
    <div class="card" id="section-targeting">
      <div class="head">🎯 Targeting</div>
      <div class="body">
        <span id="section-zones"></span>
        ${zonesHTML}
        <span id="section-dmp"></span>
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

    <!-- CREATIVES PANEL (contextual — updates when zones are selected) -->
    <div class="card" id="section-creatives">
      <div class="head">🎨 Creatives
        <span style="font-size:11px;color:var(--muted);margin-left:8px;font-weight:400">Upload one image per size required by your selected zones</span>
      </div>
      <div class="body">
        <div id="creativesPanel"><div style="padding:20px;text-align:center;color:var(--muted);font-size:11.5px">← Select zones above to see required creative sizes</div></div>
      </div>
    </div>
  `);

  // Bind all text/select inputs → syncForm
  ['f_brand', 'f_adv', 'f_obj', 'f_targetUrl',
    'f_rate', 'f_rateType', 'f_budget', 'f_daily', 'f_start', 'f_end'].forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('input', syncForm);
      el.addEventListener('change', syncForm);
    });

  refreshAudienceBar();
  // Initial render of creatives panel based on any pre-selected zones
  refreshCreativesPanel();
}

/* ══════════════════════════════════════════════════════════════════════════════
 * CREATIVE GROUP PANEL
 * Zones auto-cluster by size into group cards.
 * Each card shows zone chips (×  to ungroup) and a Merge dropdown.
 * Users upload / paste one image URL per group.
 * ══════════════════════════════════════════════════════════════════════════════ */

/** Generate a short random group ID */
function mkGroupId() { return 'g_' + Math.random().toString(36).slice(2, 9); }

/**
 * Called whenever selected zones change.
 * Reconciles formState.creativeGroups:
 *   - New zones are added to an existing group of matching size OR get a fresh solo group
 *   - Zones deselected are removed from their group; empty groups are removed
 *   - Existing groups (with URLs/labels already set) are NOT reset
 */
function refreshCreativesPanel() {
  const panel = document.getElementById('creativesPanel');
  if (!panel) return;

  const selectedPlacements = (formState && formState.placements) || [];
  const catalog = (zonesCache && zonesCache.placements) || [];

  if (!selectedPlacements.length) {
    panel.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted);font-size:11.5px">← Select zones above to see required creative sizes</div>';
    if (formState) formState.creativeGroups = [];
    return;
  }

  if (!formState.creativeGroups) formState.creativeGroups = [];
  const groups = formState.creativeGroups;

  // Step 1: remove deselected zones from every group
  for (const g of groups) {
    g.zones = g.zones.filter(z => selectedPlacements.includes(z));
  }
  formState.creativeGroups = groups.filter(g => g.zones.length > 0);

  // Step 2: add newly selected zones not yet in any group
  // Skin zones split into 3 sub-groups by zone ID pattern:
  //   *Background, *_Background  → 'skin-background'
  //   *SideLeft, *StickyLeft     → 'skin-side-left'   (465×1200 transparent)
  //   *SideRight, *StickyRight   → 'skin-side-right'  (465×1200 transparent)
  function skinSubKey(zoneId) {
    if (/SideLeft|StickyLeft/i.test(zoneId))  return 'skin-side-left';
    if (/SideRight|StickyRight/i.test(zoneId)) return 'skin-side-right';
    return 'skin-background';
  }

  const alreadyGrouped = new Set(formState.creativeGroups.flatMap(g => g.zones));
  for (const pid of selectedPlacements) {
    if (alreadyGrouped.has(pid)) continue;
    const p      = catalog.find(x => x.id === pid);
    const size   = p?.size   || 'unknown';
    const format = p?.format || 'banner';

    // Determine grouping key — skin zones split by sub-type
    const isSkinZone = size === 'skin' || format === 'skin';
    const groupKey   = isSkinZone ? skinSubKey(pid) : size;

    // Try to join existing group with matching key
    const existing = formState.creativeGroups.find(g => g._key === groupKey);
    if (existing) {
      existing.zones.push(pid);
    } else {
      // Labels and size hints for skin sub-groups
      let label = size, sizeHint = size;
      if (groupKey === 'skin-background') { label = 'Skin Background';       sizeHint = 'skin'; }
      if (groupKey === 'skin-side-left')  { label = 'Skin Left (465×1200)';  sizeHint = 'skin-left'; }
      if (groupKey === 'skin-side-right') { label = 'Skin Right (465×1200)'; sizeHint = 'skin-right'; }

      formState.creativeGroups.push({
        groupId:  mkGroupId(),
        _key:     groupKey,   // internal grouping key (not saved to DB)
        zones:    [pid],
        size:     sizeHint,
        format,
        url:      '',
        label
      });
    }
    alreadyGrouped.add(pid);
  }

  renderGroupCards(panel);
}

/** Renders all group cards into the panel DOM */
function renderGroupCards(panel) {
  const groups = formState.creativeGroups;
  if (!groups || !groups.length) {
    panel.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted);font-size:11.5px">No size metadata found for selected zones</div>';
    return;
  }

  const isSkin = s => s === 'skin' || !s.includes('x');

  panel.innerHTML = groups.map((g, gi) => {
    const gid = escHTML(g.groupId);
    const sizeLabel = escHTML(g.size || 'unknown');
    const url = g.url || '';

    // Zone chips
    const chips = g.zones.map(z =>
      `<span class="zone-chip">${escHTML(z)}<button type="button" class="chip-x" onclick="ungroupZone('${escHTML(z)}','${gid}')" title="Use separate image for this zone">×</button></span>`
    ).join('');

    // Merge dropdown options (other groups)
    const mergeOpts = groups
      .filter((_, j) => j !== gi)
      .map(og => `<option value="${escHTML(og.groupId)}">${escHTML(og.size)} (${og.zones.length} zone${og.zones.length > 1 ? 's' : ''})</option>`)
      .join('');
    const mergeBtn = mergeOpts
      ? `<span style="display:flex;align-items:center;gap:4px;margin-left:auto">
           <span style="font-size:10px;color:var(--muted)">Merge into:</span>
           <select class="ipt" style="font-size:10px;height:22px;padding:0 4px" onchange="mergeGroups('${gid}',this.value);this.value=''">
             <option value="">— pick group —</option>${mergeOpts}
           </select>
         </span>`
      : '';

    return `
    <div class="creative-group-card" id="cgcard_${gid}">
      <div class="cgcard-header">
        <span class="size-pill${isSkin(g.size) ? ' skin' : ''}">${sizeLabel}</span>
        <div class="zone-chips">${chips}</div>
        ${mergeBtn}
      </div>
      <div class="cgcard-body">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <label class="upload-btn" for="cgfile_${gid}">📤 Upload</label>
          <input type="file" id="cgfile_${gid}" accept="image/*" style="display:none"
            onchange="handleGroupUpload(this.files[0],'${gid}')">
          <input class="ipt" id="cgurl_${gid}" type="url" placeholder="or paste image URL…"
            value="${escHTML(url)}" style="flex:1;min-width:180px"
            oninput="syncGroupUrl('${gid}',this.value)">
          <img id="cgprev_${gid}" src="${escHTML(url)}" alt="" style="width:64px;height:32px;object-fit:contain;border:1px solid var(--border);border-radius:4px;background:#111;display:${url ? 'block' : 'none'}">
          <span id="cgst_${gid}" style="font-size:10px;color:var(--muted)"></span>
        </div>
        <div id="cgwarn_${gid}" style="display:none;font-size:10.5px;margin-top:4px"></div>
      </div>
    </div>`;
  }).join('');

  // Re-run image checks for groups that already have a URL
  for (const g of groups) {
    if (g.url) setTimeout(() => checkCreativeImageSize(g.url, g.size, g.groupId), 200);
  }
}

/* ── Group card actions ──────────────────────────────────────────────────────── */

/** Sync a URL change for a group card */
function syncGroupUrl(groupId, url) {
  if (!formState || !formState.creativeGroups) return;
  const g = formState.creativeGroups.find(x => x.groupId === groupId);
  if (!g) return;
  g.url = url;
  const prev = document.getElementById('cgprev_' + groupId);
  if (prev) { prev.src = url; prev.style.display = url ? 'block' : 'none'; }
  // Keep legacy creative synced to first group with a URL
  const firstWithUrl = formState.creativeGroups.find(x => x.url);
  if (firstWithUrl) formState.creative = { name: formState.brand, size: firstWithUrl.size, url: firstWithUrl.url };
  const warn = document.getElementById('cgwarn_' + groupId);
  if (!url && warn) warn.style.display = 'none';
  if (url) setTimeout(() => checkCreativeImageSize(url, g.size, groupId), 400);
}

/** Remove zone `zoneId` from group `groupId`, put it in its own new group */
function ungroupZone(zoneId, groupId) {
  if (!formState || !formState.creativeGroups) return;
  const g = formState.creativeGroups.find(x => x.groupId === groupId);
  if (!g) return;
  g.zones = g.zones.filter(z => z !== zoneId);
  // If group has no zones left, remove it entirely
  if (!g.zones.length) {
    formState.creativeGroups = formState.creativeGroups.filter(x => x.groupId !== groupId);
  }
  // Get size for this zone from catalog
  const catalog = (zonesCache && zonesCache.placements) || [];
  const p = catalog.find(x => x.id === zoneId);
  // Create solo group for the ejected zone
  formState.creativeGroups.push({
    groupId: mkGroupId(),
    zones:   [zoneId],
    size:    p?.size   || g.size,
    format:  p?.format || g.format,
    url:     '',
    label:   ''
  });
  renderGroupCards(document.getElementById('creativesPanel'));
}

/** Merge all zones of srcGroupId into destGroupId, remove src card */
function mergeGroups(srcGroupId, destGroupId) {
  if (!formState || !formState.creativeGroups || srcGroupId === destGroupId) return;
  const src  = formState.creativeGroups.find(x => x.groupId === srcGroupId);
  const dest = formState.creativeGroups.find(x => x.groupId === destGroupId);
  if (!src || !dest) return;
  // Move all zones from src → dest
  dest.zones = [...new Set([...dest.zones, ...src.zones])];
  // Remove src
  formState.creativeGroups = formState.creativeGroups.filter(x => x.groupId !== srcGroupId);
  renderGroupCards(document.getElementById('creativesPanel'));
}

/**
 * Check an image URL's actual dimensions vs. the zone's expected size.
 * Shows a warning div below the input if ratio or exact size don't match.
 * @param {string} url      - image URL
 * @param {string} sizeKey  - expected size string e.g. "1160x250", "skin"
 * @param {string} groupId  - group ID (used to find the warn div)
 */
function checkCreativeImageSize(url, sizeKey, groupId) {
  const warnId = groupId ? 'cgwarn_' + groupId : 'cwarn_' + sizeKey;
  const warnEl = document.getElementById(warnId);
  if (!warnEl) return;

  // skin zones have no fixed size — skip check
  // skin zones have no fixed size
  if (!sizeKey || sizeKey === 'skin' || !sizeKey.includes('x')) {
    warnEl.style.display = 'none';
    return;
  }

  const [expW, expH] = sizeKey.split('x').map(Number);
  if (!expW || !expH) { warnEl.style.display = 'none'; return; }
  const expRatio = expW / expH;

  const img = new Image();
  img.onload = function() {
    const actW = img.naturalWidth;
    const actH = img.naturalHeight;
    const actRatio = actW / actH;
    const ratioDiff = Math.abs(actRatio - expRatio) / expRatio;

    const exactMatch = (actW === expW && actH === expH);
    const ratioOk   = ratioDiff <= 0.15;   // within 15%
    const ratioFar  = ratioDiff >  0.40;   // worse than 40% — strong warning

    let html = '';
    let borderColor = '';

    if (exactMatch) {
      html = `<span style="color:#4caf7d">&#10003; Perfect match: ${actW}&times;${actH}px</span>`;
      borderColor = '#1a3a2a';
    } else if (ratioFar) {
      html = `<span style="color:#f87171">&#9888; Wrong ratio: image is ${actW}&times;${actH}px (ratio ${actRatio.toFixed(2)}) — ` +
             `expected ${expW}&times;${expH}px (ratio ${expRatio.toFixed(2)}). Ads may appear distorted.</span>`;
      borderColor = '#3a1a1a';
    } else if (!ratioOk) {
      html = `<span style="color:#fbbf24">&#9888; Ratio mismatch: image is ${actW}&times;${actH}px — ` +
             `expected ${expW}&times;${expH}px. Consider resizing for best results.</span>`;
      borderColor = '#2e2a14';
    } else if (!exactMatch) {
      html = `<span style="color:#60a5fa">&#8505; Size differs: image is ${actW}&times;${actH}px, expected ${expW}&times;${expH}px. ` +
             `Ratio is close — should display fine.</span>`;
      borderColor = '';
    }

    warnEl.innerHTML = html;
    warnEl.style.display = html ? 'block' : 'none';

    // Tint the row border if there's a problem
    const rowEl = warnEl.closest('.row[style*="border"]');
    if (rowEl && borderColor) rowEl.style.borderColor = borderColor.replace('#','') ? borderColor : 'var(--border)';
  };
  img.onerror = function() {
    warnEl.innerHTML = '<span style="color:#f87171">&#9888; Could not load image to verify dimensions</span>';
    warnEl.style.display = 'block';
  };
  img.src = url;
}

/* ── Form sync ─────────────────────────────────────────────────────────────────── */

function syncForm() {
  if (!formState) return;
  const g = id => { const e = document.getElementById(id); return e ? e.value : ''; };
  formState.brand = g('f_brand');
  formState.advertiser = g('f_adv');
  formState.objective = g('f_obj');
  formState.creative.name = g('f_creativeName') || formState.brand;
  formState.targetUrl = g('f_targetUrl');
  formState.rate = +g('f_rate') || 0;
  formState.rateType = g('f_rateType');
  formState.budget = +g('f_budget') || 0;
  formState.daily = +g('f_daily') || 0;
  formState.startDate = g('f_start');
  formState.endDate = g('f_end');
  formState.freqCap = g('f_freqCap');
  refreshAudienceBar();
}

/* syncCreativeRow kept for backward compat with any inline edit paths */
function syncCreativeRow(i) {
  const urlEl = document.getElementById('f_curl_' + i);
  if (!urlEl || !formState) return;
  if (formState.creatives && formState.creatives[i]) {
    formState.creatives[i].url = urlEl.value;
  }
}

/* ── Creative upload helper ──────────────────────────────────────────────────── */
function updateCreativePreview() {
  const url = (document.getElementById('f_url') || {}).value || '';
  const prev = document.getElementById('creativePrev');
  if (!prev) return;
  if (url) { prev.src = url; prev.style.display = 'block'; }
  else      { prev.style.display = 'none'; }
}

async function handleCreativeUpload(file) {
  if (!file) return;
  const statusEl = document.getElementById('uploadStatus');
  const btnEl    = document.getElementById('btnUpload');
  if (statusEl) statusEl.textContent = '⏳ Uploading…';
  if (btnEl)    btnEl.disabled = true;
  try {
    const result = await Api.uploadCreative(file);
    const urlEl = document.getElementById('f_url');
    if (urlEl) { urlEl.value = result.url; syncForm(); updateCreativePreview(); }
    if (statusEl) statusEl.textContent = `✓ Uploaded: ${result.filename}`;
    toast('✓ Creative uploaded');
  } catch (err) {
    if (statusEl) statusEl.textContent = `✗ Upload failed: ${err.message}`;
    toast('Upload error: ' + err.message, true);
  } finally {
    if (btnEl) btnEl.disabled = false;
  }
}

/** Upload handler for a creative group card */
async function handleGroupUpload(file, groupId) {
  if (!file) return;
  const statusEl = document.getElementById('cgst_' + groupId);
  if (statusEl) statusEl.textContent = '⏳ Uploading…';
  try {
    const result = await Api.uploadCreative(file);
    // Update group state and UI
    const urlInput = document.getElementById('cgurl_' + groupId);
    if (urlInput) urlInput.value = result.url;
    syncGroupUrl(groupId, result.url);
    if (statusEl) statusEl.textContent = '✓ ' + result.filename;
    toast('✓ Uploaded');
  } catch (err) {
    if (statusEl) statusEl.textContent = '✗ ' + err.message;
    toast('Upload error: ' + err.message, true);
  }
}

/* Legacy per-size upload (kept for any old code paths) */
async function handleCreativeRowUpload(file, sizeKey) {
  if (!file || !formState) return;
  // Find the group that owns this size
  const g = (formState.creativeGroups || []).find(x => x.size === sizeKey);
  if (g) { await handleGroupUpload(file, g.groupId); return; }
  toast('Upload error: no group found for size ' + sizeKey, true);
}

async function submitForm(action, status) {
  syncForm();
  if (!formState.brand) { toast('⚠ Brand is required', true); return; }
  if (!formState.creative.name) formState.creative.name = formState.brand;

  // ── Serialize creativeGroups → creatives[] ────────────────────────────────
  // Each group becomes one creative entry with a zones[] array for zone-specific serving.
  if (formState.creativeGroups && formState.creativeGroups.length) {
    formState.creatives = formState.creativeGroups.map(g => ({
      groupId: g.groupId,
      name:    g.label || g.size,
      size:    g.size,
      format:  g.format || (g.size === 'skin' ? 'skin' : 'banner'),
      url:     g.url || '',
      zones:   g.zones || [],   // zone-specific lookup in backend
    }));
    // Sync legacy creative from first group that has a URL
    const first = formState.creativeGroups.find(g => g.url);
    if (first) formState.creative = { name: formState.brand, size: first.size, url: first.url };
  }

  formState.status = status;
  const btn = document.getElementById('btnActivate');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }

  try {
    let result;
    if (action === 'create') {
      result = await Api.createOrder(formState);
      toast('✓ Created ' + result.id);
      if (result.warnings && result.warnings.length) {
        setTimeout(() => toast('⚠ ' + result.warnings.length + ' zone warning(s)'), 2500);
      }
    } else {
      result = await Api.updateOrder(editing, formState);
      toast('✓ Updated ' + editing);
    }
    editing = null;
    formState = null;
    navTo('orders');
  } catch (e) {
    const msg = e.message || 'Unknown error';
    if (msg.includes('conflict') || msg.includes('409')) {
      toast('🚫 Zone Conflict: ' + msg, true);
    } else {
      toast('Error: ' + msg, true);
    }
    if (btn) { btn.disabled = false; btn.textContent = action === 'create' ? '＋ Create & Activate' : '💾 Update & Activate'; }
  }
}

function cancelForm() {
  editing = null;
  formState = null;
  navTo('orders');
}
