# Public Experience Revamp — Current State and Evidence

Date: 2026-07-20
Starting commit: `b6da5e4d4fd58107f39a6ca12ddddcc529d33bcd`
Production build: `2026-07-20.4`

## Delivered behavior

- `/` is a public, animated, reduced-motion-safe product landing page.
- `/agent` is the durable Agent entry. Zalo callbacks and `?conversation=` deep
  links bypass the landing and preserve their return intent.
- The Agent homepage uses progressive disclosure: anonymous use is explicit;
  Zalo login is optional and primary; local email/password stays inside the
  existing testing fallback.
- Copilot and Autopilot have separate deterministic product demos with pause,
  resume, previous, next, skip, restart and exit controls.
- Both demos use local fixtures only. The legacy controller no longer sends
  chat, edits the real workspace or clicks the real order action.
- The served technical document now covers current business flow, canonical
  artifacts, hybrid RAG, Creative Intelligence, durable workers, identity,
  Zalo OA, live view, six reports/PDF, security, recovery, observability,
  deployment, limitations and roadmap.
- Mermaid diagrams retain a fullscreen zoom/lightbox; tables scroll within the
  document rather than widening the mobile viewport.

## Automated verification

- Frontend: **85 passed**, 0 failed.
- Agent: **322 passed**, 0 failed, with the two existing dependency warnings.
- Frontend production build: Vite 6.4.3, **2,586 modules transformed**.
- Focused route/demo tests cover callback/deep-link intent, anonymous/account
  copy, both state machines, no external campaign side effects and reduced
  motion.

## Browser acceptance before deployment

- Desktop landing at 1280×720: zero horizontal overflow; primary Agent, both
  demo and documentation actions are reachable.
- Mobile landing at 390×844: zero horizontal overflow; all actions stack and
  remain reachable.
- Copilot demo completed **8/8** stages.
- Autopilot demo completed **12/12** stages and ended at Zalo/web continuity.
- The demo DOM contained `data-demo-sandbox=true` and no
  `#create-campaign-btn`.
- Technical document: four Mermaid diagrams rendered; three table containers,
  zoom lightbox and `/` plus `/agent` navigation present. At 390×844 the page
  had zero document overflow, one-column contents navigation and contained
  table scrolling.

## Production deployment and rollback

- Production switched successfully to build **2026-07-20.4** on
  `agent.pawgrammers.io.vn`.
- `/`, `/tech-docs.html`, `/agent/health` and `/agent/ready` all returned
  HTTP 200 after cutover. Health reported `2026-07-20.4`; readiness reported
  Mongo, backend, creative worker, Autopilot worker, Zalo worker and Zalo
  OpenAI checks healthy.
- Signed-in browser acceptance preserved the account identity, Zalo linkage
  and all five existing campaign-history entries at `/agent`.
- The live Copilot and Autopilot sandboxes reached **8/8** and **12/12**
  respectively with `data-demo-sandbox=true`.
- Live mobile acceptance at 390x844 measured `scrollWidth=390` on the landing;
  every primary CTA remained reachable. The technical document rendered four
  Mermaid SVGs and three horizontally scrollable tables without document
  overflow, and its diagram lightbox opened successfully.
- A clean, cookie-free auth probe returned an unauthenticated identity with
  Zalo login available, while the source-level acceptance suite verifies the
  anonymous-first copy and entry flow. The signed-in browser session was not
  logged out or mutated merely to manufacture a second screenshot.
- Recoverable frontend backup:
  `/var/backups/advertising-agent/20260719T192045Z-public-experience/frontend`.
- Immediate previous frontend:
  `/var/www/agent-prev-20260720-4`.
- Previous API version file:
  `/var/backups/advertising-agent/20260719T192045Z-public-experience/version.py`.

## Current limitations preserved in public wording

- Six analytical views still use clearly labelled synthetic showcase delivery
  data, not live ad-delivery truth.
- Direct inbound Zalo creative-image ingestion remains deferred.
- `REP-004` remains blocked until an external test recipient is explicitly
  authorized.
- Qwen reranking remains disabled after the recorded relevance/latency
  regression; horizontal scale/SLO and a live optimization agent remain
  roadmap work.
