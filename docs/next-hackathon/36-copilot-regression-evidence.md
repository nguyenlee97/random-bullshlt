# Campaign Copilot regression repair evidence

Date: 2026-07-19

Branch: `revamp/next-hackathon`

Production build: `2026-07-19.5`

## Outcome

The production Campaign Copilot Brief → Audience → Creative path is working
again. Guided Audience now uses the same catalog-grounded recommendation
pipeline as Campaign Autopilot, returns unique stable segment IDs, and cannot
apply a late response to a different conversation.

No Mongo schema, data migration, account ownership rule, Zalo behavior,
campaign order, or Node backend authority changed in this repair.

## Reproduced defects

The production regression was reproduced with a complete Mixifood awareness
brief.

1. The old Guided-only selector loaded only the first 200 catalog rows and
   fuzzily mapped model labels back to catalog records. It returned eight rows
   but only six unique segment IDs, including duplicated `INT158` and
   `INT126`, and described Alcoholic beverages as a direct snack match.
2. A model clarification could return only a generic sentence ending in a
   colon, without asking for the fields listed in `missing_fields`.
3. The mounted Audience editor could retain recommendation cards from the
   previous campaign. Legacy duplicate React keys made a stale card remain
   visible after the selected proposal was replaced.
4. A slow proactive Audience request could finish after the operator switched
   campaigns and inject the old campaign's chat blocks and workspace proposal
   into the new conversation.

## Implemented repair

- `handle_audience_entry` now consumes `handle_dmp_recommend`, the shared
  RAG/legacy-fallback contract already used by Autopilot.
- Stable catalog identity deduplication is applied in the RAG selector, legacy
  fallback, Guided proposal construction, frontend normalization and legacy
  workspace hydration.
- If the provider repeats a valid label, RAG fills the gap only from the
  already-ranked and guard-approved candidate list.
- Empty grounded retrieval returns a retry message and never creates or applies
  a workspace proposal.
- Targeting remains catalog-valid and uses the shared targeting selector.
- Brief clarification renders explicit Vietnamese questions from the typed
  `missing_fields` list.
- Starting or resuming a campaign clears the previous recommendation state.
- Proactive Audience work waits for canonical workspace hydration, captures the
  conversation ID and campaign epoch, and discards its result if either changes
  before completion.

## Verification

### Automated

- Agent suite: **303 passed**, 0 failed.
- Frontend suite: **65 passed**, 0 failed.
- Focused Brief/Audience/RAG suite: **30 passed**, 0 failed.
- Production Vite build: passed; 2,582 modules transformed.
- Local and VPS Python compile checks: passed.
- Production `GET /api/version`: `2026-07-19.5`.
- Production `GET /ready`: ready; Mongo, Node backend, creative worker,
  Autopilot worker, Zalo worker and Zalo OpenAI checks all true.

### Production browser journey

The signed-in production browser was used to exercise both the original
failure and the repaired cross-conversation race.

1. Resume a completed Mixifood Guided campaign, immediately return home and
   start a new Campaign Copilot conversation.
2. Submit brand `FE-COPILOT-RACE-PASS`, Awareness, Reach 900,000, 4 million
   VND, 2026-08-28 through 2026-08-30, snack/fast-food audience.
3. Before Brief approval, verify the new proposal exists and no Mixifood
   Audience response appears.
4. Approve Brief: canonical workspace advances to revision 1.
5. Audience returns exactly six unique catalog segments:
   `INT158`, `INT168`, `INT154`, `INT164`, `INT130`, `INT157`.
   No Alcoholic beverages row or duplicate stable ID appears.
6. The chat proposal, selected cards and recommendation count all agree.
7. Approve Audience: canonical workspace advances to revision 2 and the UI
   opens Creative.
8. Delete the four disposable Copilot conversations created during
   reproduction. The original user Copilot campaign and the Mixifood/Doraemon
   Autopilot campaigns remain.

## Deployment and rollback

Only the changed Python runtime files and the built frontend were deployed.
Mongo was not reseeded, deleted or migrated.

- Agent rollback archive:
  `/var/backups/agent-api-copilot-20260719-140910.tar.gz`
- Frontend rollback archive:
  `/var/backups/agent-frontend-copilot-20260719-141415.tar.gz`

## Known follow-up

The live DMP catalog still does not provide size fields for these records, so
the UI truthfully shows “catalog chưa cung cấp size”. This repair does not
invent an audience estimate.
