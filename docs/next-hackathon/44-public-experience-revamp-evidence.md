# Public Experience Revamp — Current State and Evidence

Date: 2026-07-20
Starting commit: `b6da5e4d4fd58107f39a6ca12ddddcc529d33bcd`
Correction follows: `3d63e35`
Production build: `2026-07-20.6`

## Delivered behavior

- `/` is now a high-motion, reduced-motion-safe campaign landing page built
  around one animated campaign constellation: Agent core, audience, creative,
  placement, reporting, Zalo-style conversation and campaign artwork.
- `/agent` is a durable SPA entry, including hard navigation and refresh. An
  exact Nginx route keeps it separate from the slash-terminated `/agent/` API
  proxy.
- The Agent homepage now has a contained visual hierarchy: introduction and
  identity, a named workspace entrance, two ordered mode cards, large primary
  workspace CTAs, secondary guided-tour actions, then campaign history and the
  Zalo companion.
- The temporary slideshow demos were removed. Copilot once again uses the
  original spotlight guide over the real Chat and Workspace UI; Autopilot has
  a matching real-interface tour over its actual input canvas.
- The Copilot interactive walkthrough still exercises the real workflow, but
  it deliberately stops at launch review. No guided flow clicks the real order
  action.
- The served technical document has nine sections. Part 10, its limitations
  table and roadmap material were removed.
- The document's “Vào Agent” link now reaches
  `/agent?from=docs`. The source Nginx config and VPS both serve `/agent` as
  the SPA instead of redirecting it into the API root.
- Mermaid diagrams retain fullscreen zoom/lightbox behavior; tables remain
  contained on mobile.

## Automated verification

- Frontend: **84 passed**, 0 failed.
- Frontend production build: Vite 6.4.3, **2,586 modules transformed**.
- Focused acceptance covers the kinetic landing, clear workspace entrances,
  real Copilot spotlight targets, all Autopilot tour targets, launch safety,
  document section removal, direct Agent navigation, exact Nginx routing,
  responsive layout and reduced motion.
- The Agent behavior suite previously passed **322 tests** for the `.4`
  release. This correction changes no Agent business logic; only version
  metadata and the frontend/Nginx boundary changed.

## Production browser acceptance

- Desktop landing at 1280×720 shows the editorial hero and animated campaign
  constellation without widening the document viewport.
- The signed-in homepage shows one ordered launchpad with prominent
  “Mở Copilot workspace” and “Mở Autopilot workspace” CTAs plus two secondary
  guided-tour actions.
- An existing Copilot campaign opened without creating new campaign data. The
  top-bar Tour opened its mode chooser, launched `Demo Guide` over the real
  interface and advanced from step 1/10 to 2/10.
- The technical document exposes nine TOC entries and no section 10. A real
  browser click on “Vào Agent” navigated to `/agent?from=docs`, where the
  homepage heading and Copilot workspace CTA were present.
- Mobile acceptance at 390×844 confirms the landing CTAs stack cleanly and the
  homepage preserves its introduction → identity → workspace entrance order.
- The signed-in session, Zalo linkage and existing five campaign-history
  entries were preserved. No campaign was launched or deleted for acceptance.

## Production deployment and rollback

- Production is live at **2026-07-20.6** on
  `https://agent.pawgrammers.io.vn/`.
- `/`, `/agent`, `/tech-docs.html`, `/agent/health` and `/agent/ready` return
  HTTP 200. Health reports `.6`; readiness reports Mongo, backend, creative
  worker, Autopilot worker, Zalo worker and Zalo OpenAI healthy.
- Baseline rollback before the guided-tour release:
  `/var/backups/advertising-agent/20260719T201216Z-guided-tours`.
- Rollback immediately before `.6`, including the prior frontend, version file
  and Nginx config:
  `/var/backups/advertising-agent/20260719T202257Z-docs-navigation`.
- Immediate previous frontends remain recoverable at
  `/var/www/agent-prev-20260720-5` and
  `/var/www/agent-prev-20260720-6`.

## Current limitations preserved in public wording

- Six analytical views still use clearly labelled synthetic showcase delivery
  data, not live ad-delivery truth.
- Direct inbound Zalo creative-image ingestion remains deferred.
- `REP-004` remains blocked until an external test recipient is explicitly
  authorized.
- Qwen reranking remains disabled after the recorded relevance/latency
  regression; horizontal scale/SLO and a live optimization agent remain
  roadmap work.
