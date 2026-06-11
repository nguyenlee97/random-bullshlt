/**
 * views/create_dmp.js — DMP Audience dual-list + Audience Size Meter
 * Depends on: dmpCache, formState from app.js
 */

/**
 * Build the DMP Audience sub-section HTML.
 * @param {Array}  dmpItems  - array of {k, name, size} from API
 * @param {object} f         - current formState
 * @returns {string} HTML
 */
function buildDmpSection(dmpItems, f) {
  const items = dmpItems || [];
  const fs    = f || formState || { dmp: { include: [], exclude: [] } };
  const inc   = fs.dmp.include || [];
  const exc   = fs.dmp.exclude || [];

  function dmpList(side, selected) {
    if (!items.length) {
      return `<div style="padding:20px;text-align:center;color:var(--muted);font-size:11.5px">No DMP attributes loaded</div>`;
    }
    return items.map(a => {
      const isSel = selected.includes(a.k || a.key || a._id);
      const key   = escHTML(a.k || a.key || a._id || '');
      return `<div class="it ${isSel ? 'sel' : ''}" onclick="toggleDmp('${side}','${key}')">
        <span class="ck">${isSel ? '✓' : ''}</span>
        <span style="flex:1">${escHTML(a.name || a.segment_name || key)}</span>
        <span style="margin-left:auto;font-size:10px;color:var(--muted)">${a.size ? fmt(a.size) : ''}</span>
      </div>`;
    }).join('');
  }

  return `
    <div class="sub-section">
      <div class="sh">🧬 DMP Audience Targeting <span class="x" onclick="this.closest('.sub-section').querySelector('.sb').classList.toggle('hidden')">×</span></div>
      <div class="sb">
        <div style="margin-bottom:8px;font-size:11.5px;color:var(--muted)">
          ${items.length} segment(s) available. Search to filter.
        </div>
        <div class="dmp-grid">
          <div>
            <label>Include</label>
            <input class="ipt" id="dmpIncSearch" placeholder="Search include..." oninput="filterDmpList('include',this.value)" style="margin-bottom:6px;font-size:12px;padding:5px 8px">
            <div class="duallist" style="grid-template-columns:1fr">
              <div class="col" style="min-height:180px;max-height:220px">
                <div class="list" id="dmpIncList">${dmpList('include', inc)}</div>
              </div>
            </div>
          </div>
          <div>
            <label>Exclude</label>
            <input class="ipt" id="dmpExcSearch" placeholder="Search exclude..." oninput="filterDmpList('exclude',this.value)" style="margin-bottom:6px;font-size:12px;padding:5px 8px">
            <div class="duallist" style="grid-template-columns:1fr">
              <div class="col" style="min-height:180px;max-height:220px">
                <div class="list" id="dmpExcList">${dmpList('exclude', exc)}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>`;
}

/* ── DMP interaction ─────────────────────────────────────────────────────── */

function filterDmpList(side, query) {
  const items   = dmpCache || [];
  const listEl  = document.getElementById(side === 'include' ? 'dmpIncList' : 'dmpExcList');
  if (!listEl) return;
  const q       = query.toLowerCase();
  const selected = formState ? (formState.dmp[side] || []) : [];
  const filtered = q ? items.filter(a => (a.name || a.segment_name || '').toLowerCase().includes(q) || (a.k || a.key || '').toLowerCase().includes(q)) : items;
  listEl.innerHTML = filtered.map(a => {
    const isSel = selected.includes(a.k || a.key || a._id);
    const key   = escHTML(a.k || a.key || a._id || '');
    return `<div class="it ${isSel ? 'sel' : ''}" onclick="toggleDmp('${side}','${key}')">
      <span class="ck">${isSel ? '✓' : ''}</span>
      <span style="flex:1">${escHTML(a.name || a.segment_name || key)}</span>
      <span style="margin-left:auto;font-size:10px;color:var(--muted)">${a.size ? fmt(a.size) : ''}</span>
    </div>`;
  }).join('') || `<div style="padding:16px;text-align:center;color:var(--muted);font-size:11.5px">No match</div>`;
}

function toggleDmp(side, key) {
  if (!formState) return;
  const arr = formState.dmp[side] = formState.dmp[side] || [];
  const i = arr.indexOf(key);
  if (i < 0) arr.push(key); else arr.splice(i, 1);

  // Re-render the affected list
  const listId = side === 'include' ? 'dmpIncList' : 'dmpExcList';
  const searchId = side === 'include' ? 'dmpIncSearch' : 'dmpExcSearch';
  filterDmpList(side, document.getElementById(searchId)?.value || '');
  refreshAudienceBar();
}

/* ── Audience Size Meter ──────────────────────────────────────────────────── */

async function refreshAudienceBar() {
  if (!formState) return;
  const bar = document.getElementById('audiBar');
  if (!bar) return;

  const payload = {
    ...(formState.targeting || {}),
    dmpInclude: formState.dmp.include || [],
  };

  try {
    const est = await Api.estimateAudience(payload);
    const size     = est.size      || 0;
    const low      = est.low       || Math.round(size * 0.85);
    const high     = est.high      || Math.round(size * 1.15);
    const totalPop = est.totalPop  || 60_000_000;
    const pct      = Math.min(100, Math.round((size / totalPop) * 100));

    bar.innerHTML = `
      <div class="audi-meter">
        <div>
          <div class="lab">Estimated Audience</div>
          <div class="big">${fmt(size)}</div>
        </div>
        <div style="flex:1;min-width:120px">
          <div style="display:flex;justify-content:space-between;font-size:11px;opacity:.85;margin-bottom:5px">
            <span>${fmt(low)} (low)</span><span>${fmt(high)} (high)</span>
          </div>
          <div class="gauge"><span style="width:${pct}%"></span></div>
          <div style="font-size:10.5px;opacity:.75;margin-top:4px">${pct}% of total population (~${fmt(totalPop)})</div>
        </div>
        <div class="tag">${(formState.placements || []).length} placement(s)</div>
        <div class="tag">${(formState.dmp.include || []).length} DMP attr</div>
      </div>`;
  } catch (e) {
    // Silently fail — audience estimate is non-critical
    bar.innerHTML = `
      <div class="audi-meter" style="opacity:.6">
        <div><div class="lab">Estimated Audience</div><div class="big">—</div></div>
        <div style="flex:1"><div class="gauge"><span style="width:0%"></span></div></div>
        <div class="tag" style="font-size:10px">estimate unavailable</div>
      </div>`;
  }
}
