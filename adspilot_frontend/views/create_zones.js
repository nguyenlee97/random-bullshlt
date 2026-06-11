/**
 * views/create_zones.js — Zone/Placement dual-list picker
 * Builds the "Website Zone (Placements)" sub-section HTML
 * and provides toggle/filter interaction.
 */

/**
 * Render the zone sub-section HTML.
 * @param {object} zones   - { groups, channels, placements }
 * @param {object} f       - current formState
 * @returns {string} HTML
 */
function buildZonesSection(zones, f) {
  return `
    <div class="sub-section">
      <div class="sh">🌐 Website Zone (Placements) <span class="x" onclick="this.closest('.sub-section').querySelector('.sb').classList.toggle('hidden')">×</span></div>
      <div class="sb">
        <div style="margin-bottom:6px;font-size:11.5px;color:var(--muted)">Select placements to run ads on:</div>
        <div class="duallist">
          <div class="col">
            <input class="s" id="zoneSearchInput" placeholder="Search placement..." oninput="filterZones(this.value)">
            <div class="list" id="zoneList">${renderZoneList('', zones, f)}</div>
          </div>
          <div class="col">
            <input class="s" placeholder="Selected placements" readonly>
            <div class="list" id="zoneSel">${renderZoneSel(zones, f)}</div>
          </div>
        </div>
        <div class="radio-group" style="margin-top:8px">
          <label><input type="radio" name="dispMode" checked> Displayed on all suitable zones</label>
          <label><input type="radio" name="dispMode"> Selected zones only</label>
        </div>
      </div>
    </div>`;
}

function renderZoneList(filter, zones, f) {
  // Use cached zonesCache if zones not passed (for refresh calls)
  const z = zones || zonesCache || { groups: [], channels: {}, placements: [] };
  const fs = f || formState || { placements: [] };
  const q = (filter || '').toLowerCase();
  let html = '';

  (z.groups || []).forEach(g => {
    const groupPlacements = (z.placements || []).filter(p =>
      (g.channels || []).includes(p.channel) &&
      (!q || p.id.toLowerCase().includes(q) || g.name.toLowerCase().includes(q))
    );
    if (!groupPlacements.length && q) return;

    html += `<div class="it" style="font-weight:700;color:var(--navy);background:#fafbfd;cursor:default">
      <span style="opacity:.6">▾</span> ${escHTML(g.name)}
    </div>`;

    groupPlacements.forEach(p => {
      const sel = fs.placements.includes(p.id);
      const meta = [
        p.reach ? fmt(p.reach) : '',
        p.size  || p.format || '',
        p.vi    != null ? `VI ${p.vi}%` : '',
        p.ctr   != null ? `CTR ${p.ctr}%` : '',
        p.cpm   ? fmtVND(p.cpm) + 'đ' : '',
        p.obj   ? p.obj.toUpperCase() : '',
      ].filter(Boolean).join(' · ');

      html += `<div class="it kid ${sel ? 'sel' : ''}" onclick="togglePlacement('${escHTML(p.id)}')">
        <span class="ck">${sel ? '✓' : ''}</span>
        <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHTML(p.id)}</span>
        <span style="margin-left:6px;font-size:10px;color:var(--muted);text-align:right;flex-shrink:0;line-height:1.35">${escHTML(meta)}</span>
      </div>`;
    });
  });

  return html || `<div style="padding:20px;text-align:center;color:var(--muted);font-size:11.5px">No placements matched</div>`;
}

function renderZoneSel(zones, f) {
  const z  = zones || zonesCache || { placements: [] };
  const fs = f || formState || { placements: [] };
  if (!fs.placements.length) {
    return `<div style="padding:18px;text-align:center;color:var(--muted);font-size:11.5px">No placements selected</div>`;
  }
  return fs.placements.map(id => {
    const p = (z.placements || []).find(x => x.id === id);
    if (!p) return `<div class="it sel" onclick="togglePlacement('${escHTML(id)}')"><span class="ck">✓</span><span>${escHTML(id)}</span></div>`;
    return `<div class="it sel" onclick="togglePlacement('${escHTML(id)}')">
      <span class="ck">✓</span>
      <span style="flex:1">${escHTML(id)}</span>
      <span style="font-size:10px;color:var(--green-d);margin-left:6px">${p.size || ''} · CTR ${p.ctr || 0}%</span>
    </div>`;
  }).join('');
}

function filterZones(v) {
  const el = document.getElementById('zoneList');
  if (el) el.innerHTML = renderZoneList(v, zonesCache, formState);
}

function togglePlacement(id) {
  if (!formState) return;
  const arr = formState.placements;
  const i = arr.indexOf(id);
  if (i < 0) arr.push(id); else arr.splice(i, 1);
  const zl = document.getElementById('zoneList');
  const zs = document.getElementById('zoneSel');
  if (zl) zl.innerHTML = renderZoneList(document.getElementById('zoneSearchInput')?.value || '', zonesCache, formState);
  if (zs) zs.innerHTML = renderZoneSel(zonesCache, formState);
  refreshAudienceBar();
}
