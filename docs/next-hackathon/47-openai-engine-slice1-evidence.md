# OpenAI Engine Slice 1 — Implementation Evidence

Date: 2026-07-21

Status: deployed as build `2026-07-21.1`, uncommitted. OpenAI is not yet user-selectable.

## Delivered

- Added canonical conversational model IDs:
  - `greennode_minimax`
  - `openai_gpt_5_4_mini`
- Added a public model catalog with independent availability/status for each component.
- Added explicit environment gates so revoked GreenNode remains visible but can be disabled without enabling fallback.
- Persisted immutable model ID, lock time, and resolved model version on every new conversation.
- Added migration-safe legacy resolution to GreenNode for conversations created before model selection.
- Copied the immutable conversation model and version into every new Autopilot run.
- Added `CampaignEngineDispatcher`; GreenNode and OpenAI failures never cross-fallback.
- Kept existing GreenNode model-client and workflow internals unchanged.
- Added the `agent/openai_campaign` package with its own official OpenAI client boundary.
- Implemented schema-validated semantic `TurnDecision` planning using the locked `gpt-5.4-mini` model.
- The semantic planner receives bounded history, workspace summary, pending proposal, step, and allowed capabilities. It does not use keyword/string intent lists.
- Added homepage model selection, availability states, immutable-model explanation, create payload, resume state, and history badges.
- Kept the OpenAI selection unavailable until the independent answer/tool engine and model-purity work are complete.

## Safety properties verified

- Invalid model values are rejected.
- An OpenAI dispatch failure does not call GreenNode.
- A GreenNode run enters only the existing GreenNode handler.
- Existing conversations migrate explicitly to GreenNode instead of following a mutable default.
- New Autopilot runs preserve the conversation model lock.
- Low-confidence semantic decisions require clarification.
- Mixed questions/actions preserve read and mutation as separate subrequests.
- No mid-run model mutation API exists.

## Verification

- Complete agent suite: `331 passed`, with two pre-existing dependency/deprecation warnings.
- Complete frontend suite: `88 passed`.
- Focused model-selection frontend suite: `3 passed`.
- Production frontend build to an isolated validation directory: passed (`2586 modules transformed`).
- Python compile checks for all new model/dispatcher/OpenAI semantic modules: passed.
- The isolated build directory was removed after validation.

## Not yet delivered

- OpenAI Responses answer and function-tool loop.
- OpenAI-native brief/audience/RAG/structured-generation siblings.
- Model-purity guard that fails if an OpenAI conversation reaches `agent/llm.py`.
- Autopilot worker propagation through every model-assisted capability.
- Versioned FAQ knowledge retrieval and dynamic audience/inventory tools.
- Live OpenAI API acceptance or an enabled OpenAI campaign engine.

## Production deployment

- Live origin: `https://agent.pawgrammers.io.vn/`
- Agent build: `2026-07-21.1`
- Agent API and frontend deployed to `/var/www/agent-api` and `/var/www/agent`.
- `/agent/health`, `/agent/ready`, `/agent/api/version`, and
  `/agent/api/agent/conversation-models` returned HTTP 200 after deployment.
- Readiness confirmed Mongo, backend, Creative worker, Autopilot worker, Zalo
  worker, and Zalo OpenAI healthy.
- The live catalog reports GreenNode/MiniMax available and GPT-5.4 mini as
  `coming_soon` with `engine_not_ready`; this proves no unfinished OpenAI path
  was enabled by the deployment.
- Browser acceptance confirmed both model choices render, GreenNode is selected,
  GPT-5.4 mini is disabled as `Đang hoàn thiện`, existing campaign history keeps
  its model badge, and the browser console reported no errors.
- Rollback snapshot:
  `/var/backups/advertising-agent/20260721T073000Z-model-engine-foundation-1`
- Immediate previous frontend:
  `/var/www/agent-prev-20260721-1`

The next implementation slice is Slice 2 from technical plan 46: build the independent OpenAI Guided answer/tool loop, use `TurnDecision` before side effects, and keep the option gated until all Guided LLM call sites are OpenAI-pure.
