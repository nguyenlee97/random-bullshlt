/**
 * views/create_targeting.js — Demographics + Advance Targeting sub-sections
 */

/**
 * Build the targeting section HTML (demographics + advance targeting).
 * @param {object} tgt  - targeting options from API
 * @param {object} f    - current formState
 * @returns {string} HTML
 */
function buildTargetingSection(tgt, f) {
  const t = tgt || {};
  const fs = f || formState || { targeting: {} };
  const sel = fs.targeting || {};

  /* ── helpers ── */
  function chk(group, val) {
    return (sel[group] || []).includes(val) ? 'checked' : '';
  }
  function checkboxes(group, items) {
    return (items || []).map(v =>
      `<label class="check">
         <input type="checkbox" ${chk(group, v)} onchange="toggleTgt('${group}','${escHTML(v)}',this.checked)">
         ${escHTML(v)}
       </label>`
    ).join('');
  }
  function toggleBtns(group, items) {
    return (items || []).map(v =>
      `<button type="button"
         class="${(sel[group] || []).includes(v) ? 'on' : ''}"
         onclick="toggleTgt('${group}','${escHTML(v)}',!this.classList.contains('on'));this.classList.toggle('on')">
         ${escHTML(v)}
       </button>`
    ).join('');
  }

  /* ── Geo tree ── */
  const geoHTML = buildGeoTree(t.geo || {}, sel.geo || []);

  return `
    <!-- DEMOGRAPHICS -->
    <div class="sub-section">
      <div class="sh">👤 Demographics <span class="x" onclick="this.closest('.sub-section').querySelector('.sb').classList.toggle('hidden')">×</span></div>
      <div class="sb">

        <!-- Location -->
        <div class="row top">
          <div class="lab">Location</div>
          <div>
            <label class="check"><input type="checkbox"> Exclude location</label>
            <div style="margin-top:5px">
              <b style="font-size:11.5px">GeoDb:</b>
              <label class="check"><input type="radio" name="geodb" checked> IP2Location</label>
              <label class="check"><input type="radio" name="geodb"> Maxmind</label>
            </div>
            <div class="duallist" style="margin-top:6px">
              <div class="col">
                <input class="s" id="geoSearchInput" placeholder="Search location..." oninput="filterGeo(this.value)">
                <div class="list" id="geoList">${geoHTML}</div>
              </div>
              <div class="col">
                <input class="s" placeholder="Selected locations" readonly>
                <div class="list" id="geoSel">${renderGeoSel(sel.geo || [], t.geo || {})}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Age -->
        <div class="row top">
          <div class="lab">Age</div>
          <div class="check-grid">${checkboxes('age', t.age)}</div>
        </div>

        <!-- Gender -->
        <div class="row top">
          <div class="lab">Gender</div>
          <div>${checkboxes('gender', t.gender)}</div>
        </div>

        <!-- Device OS -->
        <div class="row top">
          <div class="lab">Device OS</div>
          <div class="check-grid">${checkboxes('deviceOS', t.deviceOS)}</div>
        </div>

        <!-- Device Brand -->
        <div class="row top">
          <div class="lab">Device Brand</div>
          <div class="check-grid">
            ${(t.deviceBrand || []).map(v =>
              `<label class="check"><input type="checkbox" ${chk('deviceBrand',v)} onchange="toggleTgt('deviceBrand','${escHTML(v)}',this.checked)"> ${escHTML(v)}</label>`
            ).join('')}
          </div>
        </div>
      </div>
    </div>

    <!-- ADVANCE TARGETING -->
    <div class="sub-section">
      <div class="sh">🎯 Advance Targeting <span class="x" onclick="this.closest('.sub-section').querySelector('.sb').classList.toggle('hidden')">×</span></div>
      <div class="sb">

        <div class="row top">
          <div class="lab">Marital status</div>
          <div class="btn-group">${toggleBtns('marital', t.marital)}</div>
        </div>

        <div class="row top">
          <div class="lab">Parental status</div>
          <div class="btn-group">${toggleBtns('parental', t.parental)}</div>
        </div>

        <div class="row top">
          <div class="lab">Education</div>
          <div class="check-grid">${checkboxes('education', t.education)}</div>
        </div>

        <div class="row top">
          <div class="lab">Income</div>
          <div class="check-grid">${checkboxes('income', t.income)}</div>
        </div>

        <div class="row top">
          <div class="lab">Career</div>
          <div class="check-grid" style="max-height:140px;overflow-y:auto;border:1px solid var(--line);padding:8px;border-radius:4px;background:#fff">
            ${(t.career || []).map(v =>
              `<label class="check"><input type="checkbox" ${chk('career',v)} onchange="toggleTgt('career','${escHTML(v)}',this.checked)"> ${escHTML(v)}</label>`
            ).join('')}
          </div>
        </div>

        <div class="row top">
          <div class="lab">Interest</div>
          <div class="check-grid" style="max-height:140px;overflow-y:auto;border:1px solid var(--line);padding:8px;border-radius:4px;background:#fff">
            ${(t.interest || []).map(v =>
              `<label class="check"><input type="checkbox" ${chk('interest',v)} onchange="toggleTgt('interest','${escHTML(v)}',this.checked)"> ${escHTML(v)}</label>`
            ).join('')}
          </div>
        </div>

        <div class="row top">
          <div class="lab">Weather</div>
          <div class="btn-group">${toggleBtns('weather', t.weather)}</div>
        </div>
      </div>
    </div>`;
}

/* ── Geo tree helpers ──────────────────────────────────────────────────────── */

function buildGeoTree(geoOpts, selectedGeo, filter) {
  const q = (filter || '').toLowerCase();
  let html = '';
  Object.keys(geoOpts).forEach(region => {
    const cities = (geoOpts[region] || []).filter(c => !q || c.toLowerCase().includes(q) || region.toLowerCase().includes(q));
    if (!cities.length) return;
    html += `<div class="it" style="font-weight:700;background:#fafbfd;cursor:default"><span style="opacity:.6">▾</span> ${escHTML(region)}</div>`;
    cities.forEach(city => {
      const isSel = (selectedGeo || []).includes(city);
      html += `<div class="it kid ${isSel ? 'sel' : ''}" onclick="toggleGeo('${escHTML(city)}')">
        <span class="ck">${isSel ? '✓' : ''}</span>
        <span>${escHTML(city)}</span>
      </div>`;
    });
  });
  return html || `<div style="padding:16px;text-align:center;color:var(--muted);font-size:11.5px">No cities matched</div>`;
}

function renderGeoSel(selectedGeo, geoOpts) {
  if (!selectedGeo || !selectedGeo.length) {
    return `<div style="padding:18px;text-align:center;color:var(--muted);font-size:11.5px">No location selected</div>`;
  }
  return selectedGeo.map(c =>
    `<div class="it sel" onclick="toggleGeo('${escHTML(c)}')"><span class="ck">✓</span><span>${escHTML(c)}</span></div>`
  ).join('');
}

function filterGeo(v) {
  const geo = targetingCache ? targetingCache.geo || {} : {};
  const el = document.getElementById('geoList');
  if (el) el.innerHTML = buildGeoTree(geo, formState ? formState.targeting.geo : [], v);
}

function toggleGeo(city) {
  if (!formState) return;
  const arr = formState.targeting.geo;
  const i = arr.indexOf(city);
  if (i < 0) arr.push(city); else arr.splice(i, 1);
  const geo = targetingCache ? targetingCache.geo || {} : {};
  const geoList = document.getElementById('geoList');
  const geoSel  = document.getElementById('geoSel');
  if (geoList) geoList.innerHTML = buildGeoTree(geo, arr, document.getElementById('geoSearchInput')?.value || '');
  if (geoSel)  geoSel.innerHTML  = renderGeoSel(arr, geo);
  refreshAudienceBar();
}

/* ── Targeting toggle (checkboxes / btn-group) ───────────────────────────── */
function toggleTgt(group, val, on) {
  if (!formState) return;
  const arr = formState.targeting[group] = formState.targeting[group] || [];
  const i = arr.indexOf(val);
  if (on  && i < 0) arr.push(val);
  if (!on && i >= 0) arr.splice(i, 1);
  refreshAudienceBar();
}
