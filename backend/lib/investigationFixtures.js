'use strict';

// Generated test documents, never publisher URLs. Only the scenario builder
// knows the preset. Investigators receive observations of these documents,
// not the preset/ground-truth label. No external resources or click requests.
function buildRuntimeFixture(config, placements) {
  if (!['click_overlay', 'healthy_baseline', 'recovery_success'].includes(config.presetId)) return null;
  if (placements.length > 100) throw new Error('runtime fixture supports at most 100 placements');
  return {
    version: 'isolated-page-v1',
    pages: Object.fromEntries(placements.map(id => {
      const overlay = config.presetId === 'click_overlay' && id === config.targetPlacementId;
      return [id, `<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; form-action 'none'; base-uri 'none'">
<style>body{margin:24px;font-family:sans-serif}#slot{position:relative;width:600px;height:180px}
#creative{width:600px;height:180px;border:0;background:#4338ca;color:white;font-size:24px}
#layer{position:absolute;inset:0;background:rgba(255,255,255,.08);pointer-events:${overlay ? 'auto' : 'none'}}</style></head>
<body><h1>Campaign preview</h1><div id="slot"><button id="creative">Discover more</button><div id="layer"></div></div>
<script>window.localEvents=[];document.getElementById('creative').addEventListener('click',()=>window.localEvents.push({type:'click'}));</script></body></html>`];
    })),
  };
}

module.exports = { buildRuntimeFixture };
