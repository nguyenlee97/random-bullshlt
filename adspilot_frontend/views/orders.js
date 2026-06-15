/**
 * views/orders.js — Orders list view
 */

async function renderOrders() {
  showLoading();
  let orders = [];
  try {
    orders = await Api.listOrders();
  } catch (e) {
    setMain(`<div class="card"><div class="body placeholder"><div class="ph-icon">⚠️</div><h3>Could not load orders</h3><p>${escHTML(e.message)}</p></div></div>`);
    return;
  }

  function stRow(s) {
    return `<span class="pill-status ${s}">${s}</span>`;
  }

  function actionBtns(o) {
    let btn = '';
    if (o.status === 'active') {
      btn = `<button class="btn xs amber" onclick="pauseFromList('${o.id}')">⏸ Pause</button>`;
    } else if (o.status === 'paused') {
      btn = `<button class="btn xs" onclick="resumeFromList('${o.id}')">▶ Resume</button>`;
    } else if (o.status === 'pending') {
      btn = `<button class="btn xs" onclick="resumeFromList('${o.id}')">✓ Activate</button>`;
    }
    return btn;
  }

  function rows(list) {
    if (!list.length) {
      return `<tr><td colspan="10" style="text-align:center;padding:32px;color:var(--muted)">No orders found</td></tr>`;
    }
    return list.map(o => `
      <tr>
        <td><b style="color:var(--navy)">${escHTML(o.id)}</b></td>
        <td>${escHTML(o.brand)}</td>
        <td><span class="pill-status" style="background:#e6f1fb;color:#185fa5">${escHTML(o.objective)}</span></td>
        <td>${(o.placements || []).length} zone(s)</td>
        <td class="tar">${fmtVND(o.budget)}đ</td>
        <td class="tar">${fmtVND(o.daily)}đ</td>
        <td style="font-size:11.5px;color:var(--muted)">${escHTML(o.startDate)} → ${escHTML(o.endDate)}</td>
        <td>${stRow(o.status)}</td>
        <td style="font-size:11.5px;color:var(--muted)">${escHTML(typeof o.updatedAt === 'string' ? o.updatedAt.slice(0,16).replace('T',' ') : '')}</td>
        <td>
          <span class="act">
            <button class="btn xs sec" onclick="editOrder('${escHTML(o.id)}')">Edit</button>
            ${actionBtns(o)}
            <button class="btn xs sec" onclick="archiveFromList('${escHTML(o.id)}')" title="Archive" style="color:var(--amber)">⊡</button>
            <button class="btn xs sec" onclick="deleteFromList('${escHTML(o.id)}')" style="color:var(--red)">×</button>
          </span>
        </td>
      </tr>`).join('');
  }

  setMain(`
    <div class="crumb"><b>All Orders</b></div>
    <div class="card">
      <div class="head">
        <span>All Orders (${orders.length})</span>
        <span class="filter-bar">
          <select class="ipt sm" id="statusFilter" onchange="filterOrdersByStatus(this.value)" style="font-size:11.5px;padding:4px 8px;width:auto">
            <option value="">All status</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="pending">Pending</option>
            <option value="draft">Draft</option>
            <option value="archived">Archived</option>
          </select>
          <button class="btn sm" onclick="navTo('create')">＋ New Order</button>
        </span>
      </div>
      <div style="overflow-x:auto">
        <table class="tbl">
          <thead>
            <tr>
              <th>Order ID</th><th>Brand</th><th>Objective</th><th>Placements</th>
              <th class="tar">Budget</th><th class="tar">Daily</th><th>Schedule</th>
              <th>Status</th><th>Updated</th><th></th>
            </tr>
          </thead>
          <tbody id="ordTbody">${rows(orders)}</tbody>
        </table>
      </div>
    </div>
  `);
}

async function filterOrdersByStatus(status) {
  const tbody = document.getElementById('ordTbody');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:20px;color:var(--muted)"><div class="spinner" style="margin:auto"></div></td></tr>`;
  try {
    const filter = status ? { status } : {};
    const orders = await Api.listOrders(filter);
    function stRow(s) { return `<span class="pill-status ${s}">${s}</span>`; }
    function actionBtns(o) {
      if (o.status === 'active') return `<button class="btn xs amber" onclick="pauseFromList('${o.id}')">⏸ Pause</button>`;
      if (o.status === 'paused') return `<button class="btn xs" onclick="resumeFromList('${o.id}')">▶ Resume</button>`;
      if (o.status === 'pending') return `<button class="btn xs" onclick="resumeFromList('${o.id}')">✓ Activate</button>`;
      return '';
    }
    if (!orders.length) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:32px;color:var(--muted)">No orders found</td></tr>`;
      return;
    }
    tbody.innerHTML = orders.map(o => `
      <tr>
        <td><b style="color:var(--navy)">${escHTML(o.id)}</b></td>
        <td>${escHTML(o.brand)}</td>
        <td><span class="pill-status" style="background:#e6f1fb;color:#185fa5">${escHTML(o.objective)}</span></td>
        <td>${(o.placements || []).length} zone(s)</td>
        <td class="tar">${fmtVND(o.budget)}đ</td>
        <td class="tar">${fmtVND(o.daily)}đ</td>
        <td style="font-size:11.5px;color:var(--muted)">${escHTML(o.startDate)} → ${escHTML(o.endDate)}</td>
        <td>${stRow(o.status)}</td>
        <td style="font-size:11.5px;color:var(--muted)">${escHTML(typeof o.updatedAt === 'string' ? o.updatedAt.slice(0,16).replace('T',' ') : '')}</td>
        <td>
          <span class="act">
            <button class="btn xs sec" onclick="editOrder('${escHTML(o.id)}')">Edit</button>
            ${actionBtns(o)}
            <button class="btn xs sec" onclick="archiveFromList('${escHTML(o.id)}')" title="Archive" style="color:var(--amber)">⊡</button>
            <button class="btn xs sec" onclick="deleteFromList('${escHTML(o.id)}')" style="color:var(--red)">×</button>
          </span>
        </td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="10" style="padding:20px;color:var(--red)">${escHTML(e.message)}</td></tr>`;
  }
}

async function pauseFromList(id) {
  try {
    await Api.pauseOrder(id);
    toast('⏸ Paused ' + id);
    renderOrders();
  } catch (e) { toast('Error: ' + e.message, true); }
}

async function resumeFromList(id) {
  try {
    await Api.resumeOrder(id);
    toast('▶ Activated ' + id);
    renderOrders();
  } catch (e) { toast('Error: ' + e.message, true); }
}

async function archiveFromList(id) {
  if (!confirm('Archive order ' + id + '?')) return;
  try {
    await Api.archiveOrder(id);
    toast('⊡ Archived ' + id);
    renderOrders();
  } catch (e) { toast('Error: ' + e.message, true); }
}

async function deleteFromList(id) {
  showConfirm(
    `Delete order ${id}? This cannot be undone.`,
    async () => {
      try {
        await Api.deleteOrder(id);
        toast('× Deleted ' + id);
        renderOrders();
      } catch (e) { toast('Error: ' + e.message, true); }
    },
    'Delete'
  );
}

async function editOrder(id) {
  editing = id;
  try {
    formState = await Api.getOrder(id);
    // Ensure nested objects exist (safety normalization)
    formState.creative   = formState.creative   || { name: '', size: '', url: '' };
    formState.targeting  = formState.targeting  || {};
    formState.dmp        = formState.dmp        || { include: [], exclude: [] };
    formState.placements = formState.placements || [];

    // ── Reconstruct creativeGroups from saved creatives[] ──────────────────
    // Priority 1: creative has zones[] → restore those exact groups
    // Priority 2: creatives with same URL → group those zones together
    // Priority 3: group by size (fallback, same as new campaign)
    formState.creativeGroups = [];
    const savedCreatives = formState.creatives || [];

    if (savedCreatives.length) {
      // Build a URL→group map for priority-2 grouping
      const urlGroupMap = {};

      for (const c of savedCreatives) {
        const hasZones = Array.isArray(c.zones) && c.zones.length > 0;

        if (hasZones) {
          // Priority 1: restore exact zone group from saved data
          formState.creativeGroups.push({
            groupId: c.groupId || ('g_' + Math.random().toString(36).slice(2, 9)),
            zones:   [...c.zones],
            size:    c.size   || 'unknown',
            format:  c.format || 'banner',
            url:     c.url    || '',
            label:   c.label  || c.name || ''
          });
        } else if (c.url) {
          // Priority 2: group zones that share the exact same image URL
          if (!urlGroupMap[c.url]) {
            urlGroupMap[c.url] = {
              groupId: c.groupId || ('g_' + Math.random().toString(36).slice(2, 9)),
              zones:   [],
              size:    c.size   || 'unknown',
              format:  c.format || 'banner',
              url:     c.url,
              label:   c.label  || c.name || ''
            };
            formState.creativeGroups.push(urlGroupMap[c.url]);
          }
          // No zones array saved → use placements of this size as best guess
          const sizePlacements = formState.placements.filter(pid => {
            // Will be cross-referenced with catalog in refreshCreativesPanel
            return true; // placeholder; refreshCreativesPanel reconciles properly
          });
          // Leave zones[] empty; refreshCreativesPanel will fill unclaimed zones
        } else {
          // Priority 3: empty creative, will be assigned by refreshCreativesPanel by size
        }
      }
    }
    // refreshCreativesPanel (called by renderCreate) will reconcile any
    // placements not yet claimed by a group, adding them by size-match.

    navTo('create');
  } catch (e) {
    toast('Failed to load order: ' + e.message, true);
  }
}

