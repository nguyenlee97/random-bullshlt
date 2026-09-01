"""Incident-scoped, read-only tools. Never expose scenario labels to a model."""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json

from evaluation.probes import InvestigationContext, run_probes


ROLE_TOOLS = {
    'performance': ('data_completeness', 'metrics_window', 'delivery_pattern', 'spend_pacing'),
    'creative': ('creative_compatibility', 'click_telemetry', 'inspect_render'),
    'setup': ('config_drift', 'creative_compatibility'),
    'placement': ('placement_benchmark', 'creative_fatigue'),
}
TOOL_DESCRIPTIONS = {
    'metrics_window': 'Compare baseline and observed impressions, clicks, CTR and spend over the incident dates. Start here for performance issues.',
    'data_completeness': 'Check missing/invalid measurements; not a telemetry endpoint.',
    'delivery_pattern': 'Compare scoped delivery and CTR over the incident measurement dates.',
    'spend_pacing': 'Compare scoped spending with baseline.',
    'creative_compatibility': 'Compare order creative metadata with catalog dimensions; not runtime rendering.',
    'click_telemetry': 'Inspect click metrics; absence of clicks does not prove a broken handler.',
    'inspect_render': 'Render the isolated test document, inspect hit targets, capture screenshot, and test local clicks. Unavailable without a fixture.',
    'config_drift': 'Compare current order with report baseline input, not a signed approval snapshot.',
    'placement_benchmark': 'Compare catalog candidates and order creative metadata. Publisher inventory/booking availability is NOT verified.',
    'creative_fatigue': 'Inspect repeat-delivery patterns; correlation only.',
}


def clean_context(ctx: InvestigationContext) -> InvestigationContext:
    # Use an allowlist, not a blacklist: no preset, flags, seed, prose, owner,
    # scenario input hash or arbitrary uploaded text enters measurement tools.
    fields = {'placementId', 'date', 'impressions', 'clicks', 'spend', 'reach',
              'conversions', 'outcomes', 'vi', 'ctr', 'cpm', 'channel', 'format'}
    clean = lambda rows: [{k: deepcopy(v) for k, v in row.items() if k in fields} for row in rows]
    return replace(ctx, baseline_records=clean(ctx.baseline_records), active_records=clean(ctx.active_records))


async def inspect_document(html: str) -> dict:
    """Only backend-generated local documents; no URL navigation or real clicks.

    Independent DOM observations are produced by Chromium, not by reading a
    scenario flag. Browser routing/CSP both deny external requests.
    """
    if not isinstance(html, str) or len(html.encode()) > 64_000:
        raise ValueError('invalid test document')
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(viewport={'width': 700, 'height': 320},
                                                service_workers='block', accept_downloads=False)
            await context.route('**/*', lambda route: route.abort())
            page = await context.new_page()
            page.set_default_timeout(5000)
            await page.set_content(html, wait_until='domcontentloaded', timeout=5000)
            observations = await page.evaluate('''() => {
                const el = document.getElementById('creative');
                if (!el) return {element_present:false};
                const r = el.getBoundingClientRect(), s = getComputedStyle(el);
                const points = [[.5,.5],[.2,.2],[.8,.2],[.2,.8],[.8,.8]].map(([x,y]) => {
                    const px = r.x + r.width*x, py = r.y + r.height*y;
                    const top = document.elementFromPoint(px,py);
                    return {x:px,y:py,target:top?.id || top?.tagName || null,
                            reaches_creative:!!top && (top===el || el.contains(top))};
                });
                return {element_present:true, width:r.width, height:r.height,
                    visible:s.display!=='none' && s.visibility!=='hidden' && r.width>0 && r.height>0,
                    points, local_clicks_before:(window.localEvents||[]).length};
            }''')
            if observations.get('points'):
                center = observations['points'][0]
                await page.mouse.click(center['x'], center['y'])
                observations['local_clicks_after'] = await page.evaluate('(window.localEvents||[]).length')
            png = await page.screenshot(type='png')
            blocked = observations.get('visible') and any(not p['reaches_creative'] for p in observations.get('points', []))
            return {'probe_id': 'inspect_render', 'source': 'isolated_browser_observation',
                    'status': 'anomaly' if blocked or not observations.get('visible') else 'ok',
                    'summary': 'Chromium hit-test and local interaction observations; no publisher request sent.',
                    'finding': 'hit_target_mismatch' if blocked else 'render_observed',
                    'evidence': observations, 'document_hash': hashlib.sha256(html.encode()).hexdigest(),
                    'screenshot_base64': base64.b64encode(png).decode()}
        finally:
            await browser.close()


class EvidenceTools:
    def __init__(self, ctx: InvestigationContext, revision: int, fixture: dict | None, *, renderer=None):
        self.ctx = clean_context(ctx)
        self.revision = revision
        self.fixture = fixture or {}
        self.renderer = renderer or inspect_document

    async def execute(self, role: str, tool: str) -> dict:
        if tool not in ROLE_TOOLS.get(role, ()):
            raise PermissionError('tool is not allowed for this specialist')
        if tool == 'metrics_window':
            def totals(rows):
                rows = self.ctx.recent(rows)
                value = {key: sum(float(row.get(key) or 0) for row in rows)
                         for key in ('impressions', 'clicks', 'spend')}
                value['ctr'] = value['clicks'] / value['impressions'] if value['impressions'] else None
                return value
            result = {'probe_id': tool, 'status': 'ok' if self.ctx.recent(self.ctx.active_records) else 'unavailable',
                      'source': 'report_dataset', 'summary': 'Same-window measured totals, not a causal diagnosis.',
                      'evidence': {'baseline': totals(self.ctx.baseline_records), 'observed': totals(self.ctx.active_records),
                                   'dates': self.ctx.evaluation_dates}}
        elif tool == 'inspect_render':
            html = (self.fixture.get('pages') or {}).get(self.ctx.scope)
            if self.fixture.get('version') != 'isolated-page-v1' or not html:
                result = {'probe_id': tool, 'status': 'unavailable', 'source': 'isolated_browser_observation',
                          'summary': 'No isolated document for this scope; publisher runtime not inspected.', 'evidence': {}}
            else:
                result = await self.renderer(html)
        else:
            result = run_probes(self.ctx, [tool])[tool]
        result = deepcopy(result)
        identity = json.dumps([self.ctx.campaign_id, self.revision, self.ctx.scope, tool, result], sort_keys=True)
        result.update({'evidence_id': 'EVD-' + hashlib.sha256(identity.encode()).hexdigest()[:20],
                       'campaign_id': self.ctx.campaign_id, 'scope': self.ctx.scope,
                       'dataset_revision': self.revision, 'observed_at': datetime.now(timezone.utc).isoformat(),
                       'tool_version': 'readonly-v1'})
        return result


def model_evidence(evidence: dict) -> dict:
    return {key: value for key, value in evidence.items() if key != 'screenshot_base64'}
