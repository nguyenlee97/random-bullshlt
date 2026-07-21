# OpenAI Guided Free-form Slice 2 — Evidence

Date: 2026-07-21

Status: deployed and production-verified as Agent build `2026-07-21.2`.

## Delivered

- Independent `AsyncOpenAI` Responses API answer/tool loop using the locked
  `gpt-5.4-mini` campaign model.
- Schema-validated semantic `TurnDecision` before answer or tool execution.
- FAQ, workflow action, mixed request, and clarification behavior based on
  model understanding rather than string matching.
- Strict OpenAI-owned function schemas with `additionalProperties=false` and
  every property required; optional values use nullable types.
- Bounded tool rounds/calls, `parallel_tool_calls=false`, `store=false`, hashed
  safety identifiers, bounded history, output tokens, timeout, and retry.
- Read-only tools for DMP discovery, ad-zone catalog/availability, targeting
  options, workflow explanations, and order status.
- Mutation tool that accepts only a field plus JSON value, resolves every
  audience/zone/creative reference through authoritative catalogs, and creates
  a durable proposal without applying it.
- Semantic approval and rejection operate only on an existing server-side
  pending proposal.
- Provider failures return an OpenAI-specific unavailable response and never
  cross-fallback to GreenNode.
- Structured decision/completion telemetry records route, confidence, tools,
  duration, model response ID, and whether a proposal was created.

## Safety properties

- Low-confidence decisions perform no answer call, tool call, or mutation.
- Generic FAQ answers do not receive the mutation tool.
- Live/catalog questions are forced through an authoritative read tool.
- Mutation requests are forced through the validated proposal tool.
- Proposals remain visible even if the final OpenAI summarization call fails.
- Tool schemas accept no browser-supplied owner, identity, or account IDs.
- `OPENAI_CAMPAIGN_ENGINE_IMPLEMENTED` remains false, so the selector cannot
  enable an incomplete end-to-end OpenAI campaign.

## Verification

- Focused Slice 1–2 suite: `18 passed`.
- Complete Agent suite: `340 passed`, with two pre-existing warnings.
- Python compile checks: passed.

## Remaining before OpenAI can be selected

- Slice 3: add OpenAI siblings and explicit provider dispatch to every
  model-backed Guided entry point while preserving the GreenNode component,
  plus a hard model-purity test.
- Slice 4: propagate the locked model through every Autopilot worker/chat task.
- Only after both slices pass may the catalog report GPT-5.4 mini as available.

## Production deployment and acceptance

- Live origin: `https://agent.pawgrammers.io.vn/`
- Agent build: `2026-07-21.2`
- `/agent/health`, `/agent/ready`, `/agent/api/version`, and the conversation
  model catalog returned HTTP 200 after restart.
- Readiness confirmed Mongo, backend, Creative worker, Autopilot worker, Zalo
  worker, and the existing Zalo OpenAI controller healthy.
- A production-key smoke test passed both:
  - schema-parsed `TurnDecision` for a Vietnamese FAQ;
  - forced strict `explain_step` function call, server execution,
    `function_call_output`, and final Vietnamese answer.
- The public model catalog still reports GPT-5.4 mini as `coming_soon` with
  `engine_not_ready`, as required until Slices 3–4 finish.
- Browser acceptance confirmed both model cards, disabled OpenAI state, account
  history/model badges, and zero console errors.
- Rollback snapshot:
  `/var/backups/advertising-agent/20260721T085256Z-openai-guided-freeform-2`
