# OpenAI Autopilot Model Purity Slice 4 — Evidence

Date: 2026-07-21

Status: deployed and production-verified as Agent build `2026-07-21.4`.

## Delivered

- Added explicit Autopilot dispatch from the model stored on each run. GreenNode
  keeps its existing audience and Q&A implementation; OpenAI uses independent
  sibling handlers under `agent/openai_campaign/`.
- Persisted the owning conversation's immutable model on every new Autopilot
  run. Legacy runs without a model backfill once from their owning conversation,
  then store the resolved value before work continues.
- Kept retry, resume, and worker execution bound to the persisted run model even
  if runtime defaults later change.
- Added an OpenAI-owned audience recommendation path and a read-only completed-run
  Q&A path using `gpt-5.4-mini` structured output.
- Made provider failures fail closed with a deterministic current-run summary;
  no OpenAI-to-GreenNode or GreenNode-to-OpenAI fallback occurs.
- Added an explicit Zalo Autopilot channel-model policy instead of inheriting a
  mutable campaign default.
- Enabled the full OpenAI campaign-engine readiness gate after both Guided and
  Autopilot model-purity suites passed.

## Model-purity evidence

- OpenAI Autopilot audience tests replace the GreenNode audience handler with a
  fail-fast sentinel and complete through the OpenAI sibling.
- Completed-run OpenAI Q&A tests replace the GreenNode generator with a fail-fast
  sentinel and complete through the OpenAI sibling.
- Provider-error tests prove the selected component never invokes its sibling as
  a fallback.
- Legacy migration tests prove a missing run model is persisted from the owning
  conversation.
- Retry tests prove an existing run retains its stored model after defaults are
  changed.
- Zalo tests prove new runs receive the configured channel policy explicitly.

## Verification

- Slice 4 Autopilot model-purity suite: `7 passed`.
- Focused OpenAI/model-routing suite: `92 passed`.
- Complete canonical Agent suite: `353 passed`, with two pre-existing warnings.
- Frontend suite: `88 passed`.
- Frontend production build: passed (existing Vite chunk-size warning only).
- Python compile checks and `git diff --check`: passed.

## Production deployment and acceptance

- Live origin: `https://agent.pawgrammers.io.vn/`
- Agent build: `2026-07-21.4`
- `/agent/health`, `/agent/ready`, `/agent/api/version`, and
  `/agent/api/agent/conversation-models` returned healthy responses after the
  PM2 restart.
- Readiness confirmed Mongo, backend, Creative worker, Autopilot worker, Zalo
  worker, and Zalo OpenAI controller healthy.
- The production catalog shows both sibling components: OpenAI is available and
  selected by default; GreenNode is visible but temporarily unavailable with
  `provider_disabled`. Its code and configuration are preserved.
- A production-key OpenAI completed-run Q&A smoke passed with
  `gpt-5.4-mini` and the `autopilot_readonly_answer` structured schema.
- A production-key OpenAI Autopilot audience smoke loaded 310 catalog segments
  and returned six recommendations through the independent OpenAI path.
- Both smokes used synthetic inputs and created no user or campaign data.
- Signed-in browser acceptance confirmed both model cards, immutable-model copy,
  OpenAI selected, GreenNode disabled as temporarily unavailable, and existing
  campaign history retaining its original GreenNode badges. The browser console
  contained no errors.
- PM2 reported `agent-api` online with zero unstable restarts.

## Production configuration and rollback

Production currently uses:

```text
OPENAI_CAMPAIGN_ENABLED=true
GREENNODE_CAMPAIGN_ENABLED=false
ZALO_AUTOPILOT_CONVERSATION_MODEL=openai_gpt_5_4_mini
```

`GREENNODE_CAMPAIGN_ENABLED=false` is an availability switch for the revoked
provider key; it does not remove or redirect the GreenNode component. Restore
that flag when the provider key is usable again.

Rollback snapshot:

```text
/var/backups/advertising-agent/20260721T095440Z-openai-autopilot-4
```
