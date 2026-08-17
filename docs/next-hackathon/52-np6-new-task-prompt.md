# NP-6 New Task Prompt

Copy the prompt below into a new Codex chat.

---

We are starting **NP-6 — Placement Catalog Expansion** for the Advertising Agent project.

Repository:

`C:\Users\LENOVO\Downloads\Claw-a-thon-20260605T160536Z-3-001\random-bullshlt`

Before doing anything:

1. Read `AGENTS.md` and the full relevant project knowledge base under `docs/knowledge base`.
2. Read:
   - `docs/next-hackathon/45-openai-creative-knowledge-roadmap.md`
   - `docs/next-hackathon/47-np2-np5-delivery-and-manual-acceptance.md`
   - `docs/next-hackathon/46-openai-engine-technical-implementation-plan.md`
   - `docs/next-hackathon/51-np6-placement-catalog-expansion-handoff.md`
3. Inspect the current Git branch, HEAD, dirty files, tests, and deployed version. The handoff is a snapshot, so revalidate it rather than assuming it is still current.
4. Preserve every unrelated modified or untracked file. Do not commit, overwrite, or delete user-owned work.

NP-6 objective:

Create a larger, realistic, **versioned and provenance-aware image placement catalog** shared by the backend, Agent, Copilot, Autopilot, Creative Studio, FAQ/live-data tools, Zalo OA, AdsPilot, reports, and test-site previews. Existing campaigns must remain reproducible against their historical catalog meaning.

Critical boundaries:

- Do not implement NP-7 video in this task.
- Do not add video codecs, audio, captions, transcoding, video generation, or a video quota.
- Do not change or merge the independent GreenNode and OpenAI campaign-engine components.
- Do not change immutable per-run model selection.
- Do not expose raw Mongo/database access to an LLM.
- Do not present synthetic price, reach, or availability as authoritative live inventory.
- Do not solve this by adding another hardcoded frontend or Zalo-specific placement list.
- Preserve the existing audience-reach, GPT Image 2 quota, FAQ/action, report-evidence, ownership, confirmation, and order-idempotency contracts.

Start with a **read-only discovery and architecture pass**. Trace every placement source and consumer, including:

- `backend/seed/data/Ads Zone.xlsx`
- `backend/models/Zone.js`
- `backend/routes/zones.js`
- `backend/middleware/zoneValidator.js`
- `agent/tools/zone_catalog.py`
- `agent/tools/zone_ranker.py`
- `agent/autopilot/placement_planning.py`
- `agent/openai_campaign/knowledge.py`
- `agent/openai_campaign/read_tools.py`
- order guard, forecasting, creative compatibility, and assignment code
- `agent_frontend/src/data/zones.js`
- Guided/Autopilot setup and result components
- AdsPilot and the ZNews/BaoMoi/ZingMP3 replicated test sites
- existing placement, inventory, FAQ, creative, order, frontend, and Zalo tests

For the first response, do not edit code or data. Produce:

1. A current source-of-truth map showing where placement IDs, dimensions, pricing, reach, availability, preview URLs, and compatibility rules come from.
2. A duplication/drift risk assessment.
3. A proposed canonical versioned placement schema.
4. A proposed small first tranche of new placements, with provenance classification:
   - authoritative;
   - partner fixture;
   - demo fixture.
5. A list of product decisions you need from me, especially publishers/properties, number of zones, pricing/reach policy, availability semantics, and preview requirements.
6. A detailed implementation plan split into safe slices with migrations, rollback, tests, production verification, and explicit NP-7 exclusions.

Do not infer or invent current publisher specifications. If current external specifications are needed, verify them from official primary sources and cite them.

After I approve the plan and initial catalog set, implement NP-6 end to end. Run focused and full maintained test suites, add historical-reproducibility and compatibility coverage, commit only NP-6 files, push the branch, back up production targets, deploy, and verify production through Guided, Autopilot, FAQ/live-data, and read-only Zalo scenarios.

Lead with concrete repository evidence. If older documentation conflicts with current code, current code/tests and verified production behavior win.

---
