# OpenAI Guided Model Purity Slice 3 — Evidence

Date: 2026-07-21

Status: deployed and production-verified as Agent build `2026-07-21.3`.

## Delivered

- Preserved the existing GreenNode Guided handlers and model client unchanged.
- Added independent OpenAI sibling handlers for brief normalization, audience
  planning, DMP recommendation, audience-entry targeting, RAG query rewriting,
  and structured output generation.
- Added explicit dispatch by the conversation's immutable
  `conversation_model` at every model-backed Guided entry point.
- Kept deterministic catalog, session, validation, and workflow services shared
  where they do not call a model.
- Added an OpenAI-owned `responses.parse` boundary with `store=false`, hashed
  safety identifiers, configured reasoning effort, and provider/model/token
  provenance.
- Injected the OpenAI selector and query rewriter into the shared deterministic
  RAG pipeline. The OpenAI route disables the configured GreenNode Qwen
  reranker and uses deterministic RRF ordering.
- Kept provider failures inside their selected component. There is no automatic
  OpenAI-to-GreenNode or GreenNode-to-OpenAI fallback.

## Model-purity evidence

- Static tests reject imports from the GreenNode model client, legacy Guided
  handlers, and GreenNode LangGraph structured generator inside
  `agent/openai_campaign/`.
- Dynamic dispatcher tests prove an OpenAI conversation invokes only the
  OpenAI handler.
- Router tests prove OpenAI brief and audience form submissions cannot invoke
  the legacy GreenNode handlers.
- Brief, audience, DMP, and RAG tests replace GreenNode model functions with
  fail-fast sentinels and complete successfully.
- The RAG test verifies that the OpenAI route supplies its own selector and
  query rewriter with `use_reranker=false`.

## Verification

- Slice 3 model-purity suite: `6 passed`.
- Focused OpenAI/dispatch suite: `38 passed`.
- Complete canonical Agent suite: `346 passed`, with two pre-existing warnings.
- Frontend suite: `88 passed`.
- Frontend production build, Python compile checks, and `git diff --check`:
  passed.

## Production deployment and acceptance

- Live origin: `https://agent.pawgrammers.io.vn/`
- Agent build: `2026-07-21.3`
- `/agent/health`, `/agent/ready`, `/agent/api/version`, and the conversation
  model catalog returned healthy responses after the PM2 restart.
- Readiness confirmed Mongo, backend, Creative worker, Autopilot worker, Zalo
  worker, and the existing Zalo OpenAI controller healthy.
- A production-key smoke test passed the new independent OpenAI structured
  generation path with `gpt-5.4-mini`; no campaign or user data was used.
- A remote purity smoke imported the new component, checked its forbidden-import
  boundary, and proved explicit dispatch selected only the OpenAI handler.
- Browser acceptance confirmed the public experience and account workspace load,
  GreenNode remains selected and available, OpenAI remains disabled with
  `Đang hoàn thiện`, existing campaign model badges are intact, and the browser
  console contains zero errors.
- The OpenAI catalog entry intentionally remains `coming_soon` with
  `engine_not_ready` until Slice 4 is complete.
- Rollback snapshot:
  `/var/backups/advertising-agent/20260721T092613Z-openai-guided-purity-3`

## Follow-up status

Slice 4 is now complete. OpenAI is selectable for new campaigns, and GreenNode
remains a separate preserved component whose availability is controlled by its
own runtime flag. See `50-openai-autopilot-model-purity-evidence.md` for the
Autopilot propagation, production smoke, and browser acceptance evidence.
