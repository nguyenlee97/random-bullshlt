# NP-2 to NP-5 delivery and manual acceptance

Status: implemented for production build `2026-07-21.13`.

## NP-2 — canonical unique audience reach

- One server-owned `/api/agent/audience/reach` contract serves Guided, Autopilot and the browser.
- Segment IDs are deduplicated. Unknown sizes remain unavailable rather than becoming zero.
- The fallback is explicitly a calibrated estimate because the current catalog has marginal ranges but no real overlap/union service.
- Every response includes range, method, universe, confidence, source freshness, catalog version and estimate version.
- The browser no longer performs or fabricates audience-union arithmetic.

## NP-3 — OpenAI Creative Studio

- GreenNode conversation code is unchanged and remains an independent selectable component.
- Both conversation engines use the same direct OpenAI GPT Image 2 creative service.
- Daily quota is 20 succeeded/reserved outputs per authenticated user or anonymous actor in Asia/Ho_Chi_Minh, shared across Copilot and Autopilot.
- Reservations are atomic and durable. Definite local/provider rejection releases quota; ambiguous provider outcomes remain reserved and auditable without a blind retry.
- Named, owned reference assets support kind, name, use instruction, required flag, moderation/lifecycle metadata and soft deletion.
- GPT-5.4-mini composes schema-validated prompt specifications without spending image quota.
- Generation records model, prompt fingerprint/version, job/request IDs, proxy size, exact final size and asset IDs.
- GPT-5.4-nano performs visual QA on generated Autopilot assets.

## NP-4 — semantic FAQ and action coordination

- GPT-5.4-mini produces a typed decision: FAQ, workflow action, mixed request or clarification.
- The decision is based on message meaning, recent context, pending proposals and workspace state; string equality is not used for routing.
- Static FAQ, catalog discovery and live-system questions use separate allowlisted read tools.
- Read-only FAQ cannot receive the workspace proposal tool and therefore cannot mutate revision, confirmations or selected campaign values.
- Mixed turns answer the read portion and create a visible proposal; the normal confirmation guard still owns application.
- The curated knowledge base is source-controlled and returns source ID, version, update date and freshness.
- Current audience counts and zone availability are queried through narrow domain services; there is no arbitrary database tool.

## NP-5 — report comprehension and evidence

- Report generation is a fixed OpenAI GPT-5.4-mini specialist, independent from both campaign conversation components.
- `report-evidence-v1` computes metric definitions, formulas, timeframe, source, findings, confidence and limitations deterministically from report records.
- Generated analysis must cite known finding IDs and metric IDs. Invented IDs fail validation rather than being stored as ready.
- OpenAI-locked report chat uses semantic structured Q&A with evidence citations; GreenNode retains its independent existing report matcher.
- The UI exposes the synthetic-showcase label, evidence source, formulas and limitations.
- LDP is explicitly deferred: the acronym has no agreed product definition. Owner: product owner. Reason: implementation would be guesswork without the expansion, target screen and expected behavior. The Agent asks for clarification and does not invent a definition.

## Manual production checklist

### Audience

1. Start a GPT-5.4-mini Copilot campaign and select one audience segment. Confirm a unique reach, range, method and confidence appear.
2. Add the same segment twice through any available recovery/edit path. Confirm reach does not increase.
3. Select several large segments. Confirm reach never exceeds the 60M configured universe and is not their simple sum.
4. Search an audience topic in chat, then ask for the count of one returned segment. Confirm the answer uses a real segment ID and identifies its source/freshness.

### Creative Studio

1. Open Creative and choose AI generation. Confirm `20/20 lượt hôm nay` (or the actor's current remainder) is visible.
2. Select a format, add creative direction, then compose the prompt. Confirm quota does not decrease.
3. Upload a named logo or product asset with a use instruction and select it.
4. Tick the one-output quota confirmation and generate. Confirm one quota is used, crop/scale review opens, and the saved creative has the exact placement dimensions.
5. Refresh/resume the conversation. Confirm the remaining quota and named asset are durable.
6. Start Autopilot with AI generation, creative direction and selected assets. Confirm it uses the same daily quota and reaches creative review with provenance.

### FAQ and actions

1. Ask `Frequency cap là gì và nên đặt thế nào?`. Confirm a grounded answer cites `ad-operations-faq` and does not change workspace revision.
2. Ask which audience covers food or gaming. Confirm catalog segments come from the live DMP catalog; no invented segment appears.
3. Ask whether a concrete zone is free for exact dates. Confirm availability is only claimed after a live conflict check.
4. Ask a mixed request such as `Zone nào phù hợp và nếu zone đầu còn trống thì đề xuất chọn nó`. Confirm the answer separates current facts from a pending proposal and does not apply it before approval.
5. Send ambiguous `làm cái đó đi` without a pending proposal. Confirm the Agent asks one clarification instead of mutating state.

### Reports

1. Launch or open a campaign report and allow the six analyses to regenerate under `report-evidence-v1`.
2. Confirm the yellow synthetic-showcase label remains visible.
3. Expand `Nguồn số liệu, công thức & giới hạn`; verify timeframe, formulas and the summed-daily-reach warning.
4. Ask a paraphrased question that does not match a predefined title. Confirm semantic Q&A answers with finding/metric citations.
5. Ask for an unavailable value or causal conclusion. Confirm the Agent says it is unavailable/unsupported rather than inventing it.

### Component isolation

1. Start one OpenAI campaign and one GreenNode campaign when GreenNode becomes available.
2. Confirm the model is locked after each run starts and there is no mid-run selector.
3. Confirm a GreenNode provider outage does not redirect its run into OpenAI, and an OpenAI outage does not redirect into GreenNode.
4. Confirm both runs still use direct OpenAI GPT Image 2 for creative generation and share the actor's daily image quota.
