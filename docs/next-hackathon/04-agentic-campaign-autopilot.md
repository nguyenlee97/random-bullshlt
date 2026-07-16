# Agentic Campaign Autopilot — Product and Technical Design

## 1. Decision summary

The next version should open with an explicit experience-mode choice before campaign work begins:

1. **Traditional Guided Workflow** — preserves the familiar step-by-step workspace. Campaign Copilot remains available inside it, so the user can edit any part through chat or the form while controlling progression manually.
2. **Campaign Autopilot** — a separate fully agentic experience. The user provides one brief, chooses an approval policy, and the agent plans and executes the reversible work from brief analysis through an order-ready campaign and post-launch reporting.

The opening mode selector answers **how the campaign will be built**. The approval policy shown after entering Autopilot answers **how much reversible work the agent may approve automatically**. These are separate decisions.

This is a core product architecture, not an optional demo widget. The theme-specific hero feature in M5 should become one capability used by Autopilot, for example strategy simulation.

“Auto approve” means the agent may automatically accept reversible recommendations inside user-defined policy. Creating an order, spending budget, publishing creatives, or overriding a safety verdict remains an explicit human approval. This keeps the experience agentic without hiding consequential actions.

## 2. Why the current implementation is not enough

The repository already has useful LangGraph scaffolding, but current auto mode is only a prototype:

- It starts from trigger phrases and requires a brief to already exist in session state.
- The planner creates a short tool list, but the results are not committed as a coherent workspace revision.
- The current workspace is split between frontend state, `agent_sessions.form_state`, graph checkpoints, and pending proposals.
- A single `step` integer and `confirmed_steps` list assume a mostly linear wizard.
- Freeform updates can be based on stale frontend snapshots and depend heavily on keyword confirmation.
- Auto mode produces a review summary but does not provide durable task progress, pause/resume, replanning, or recovery.
- The current critic can fail open. That is acceptable for an advisory summary, but not for a launch-capable workflow.
- The user cannot inspect a durable plan, see evidence per task, cancel safely, or resume after restart.

The fix is not a larger prompt. It is a transactional workspace, a dependency-aware artifact model, and a durable run engine.

## 3. Intended user experience

### 3.0 Experience selection

Before showing the campaign workspace, present two clear cards:

- **Traditional Workflow** — “Build the campaign step by step with AI assistance.” Opens the existing Brief → Audience → Creative → Setup → Result workflow with Copilot chat.
- **Campaign Autopilot** — “Give the agent a brief and review its work as it builds the campaign.” Opens a brief-first Autopilot intake and then the plan/approval screen.

Store the selection as `experience_mode: guided | autopilot` on the workspace. Guided mode does not start an agent run. Autopilot mode creates a durable run only after the brief is accepted and the user confirms an approval policy.

Changing mode after work has begun must show an impact preview. Guided → Autopilot may reuse valid approved artifacts; Autopilot → Guided pauses the run and opens the current artifacts in the step-by-step workspace. No artifact may be silently discarded.

### 3.1 Copilot mode

The user may say, in Vietnamese or English:

- “Đổi ngân sách thành 40 triệu.”
- “Giữ audience hiện tại nhưng bỏ nhóm sinh viên.”
- “Chọn creative trước, tôi sẽ bổ sung brief sau.”
- “Vì sao em chọn các zone này?”
- “Quay lại sửa ngày chạy nhưng giữ creative.”

The agent responds with one of four explicit outcomes:

- **Answer** — explanation only; no state change.
- **Proposal** — shows old value, new value, reason, affected downstream artifacts, and Approve/Reject controls.
- **Applied safe action** — only when the user has already granted the applicable approval policy.
- **Blocked request** — explains missing data or a safety/business constraint and gives the smallest next action.

### 3.2 Autopilot mode

The ideal flow is:

1. User selects **Campaign Autopilot** on the opening screen.
2. User pastes a campaign brief or uploads a brief document.
3. Agent extracts structured requirements and asks only questions that block execution.
4. Agent shows a task plan, expected outputs, approval checkpoints, and an estimated runtime.
5. User chooses an approval policy:
   - **Review every stage** — approve brief, strategy, audience/targeting, creative, placement, and final order.
   - **Review critical stages** — recommended; auto-approve high-confidence reversible tasks, pause for ambiguity, creative review, policy exceptions, and final launch.
   - **Auto-build draft** — execute every reversible task automatically and stop at an order-ready draft.
6. Agent runs tasks and streams progress: queued, running, completed, needs review, blocked, failed, or cancelled.
7. The user can change a requirement at any time. The agent pauses, computes impact, invalidates only dependent artifacts, replans, and resumes.
8. Agent presents a final diff and evidence package. One explicit confirmation creates the idempotent order.
9. Agent verifies the order and produces an initial setup report. Performance analysis is generated only when real or clearly labelled simulated data exists.

### 3.3 Codex-like qualities to copy

- A visible plan rather than hidden chain-of-thought.
- Live progress with the current action and result.
- Evidence links and IDs for every grounded decision.
- Clear approval boundaries.
- Pause, cancel, resume, retry, and replan.
- Reuse of completed work when requirements change.
- A final summary of what changed, what was verified, and what remains.

The UI must not expose private model reasoning. It exposes task rationale, evidence, decisions, and validation results.

### 3.4 Creative source is an explicit run input

Before an Autopilot run starts, the operator must choose one creative-source policy:

- `upload`: the run pauses at `prepare_creatives` until a canonical uploaded file exists.
- `ai_generate`: the durable worker creates, resizes, stores and commits an AI-generated creative, then submits it to the same deterministic and VLM analysis path used for uploads.

The first implementation generates one exact-size `zuma-box` 300×250 asset. Its storage key includes the run ID, format and brief revision; retries recover the deterministic stored asset instead of generating another image. Provider, model, prompt version, prompt fingerprint and format are persisted as provenance.

Creative generation is not creative approval. A safety warning, low-confidence verdict or VLM timeout still pauses for a human. All approval policies still stop at the final launch gate before order creation. Multi-format generation is a later slice and must be placement-aware, cost-bounded and idempotent.

## 4. Core safety and consistency invariants

These rules are non-negotiable:

1. MongoDB holds the canonical campaign workspace. The frontend is a rendered client, not a second source of truth.
2. The model never writes arbitrary workspace JSON. It emits a typed domain command or proposal.
3. Every mutation includes `workspace_id`, `base_revision`, actor, reason, and idempotency key.
4. The server validates the command, checks the expected revision, computes dependency impact, then applies it atomically.
5. A stale revision returns a conflict and fresh diff; it is never silently overwritten.
6. Every visible chat message, proactive event, proposal, approval, rejection, and task result is durably recorded.
7. Every catalog-derived audience or zone retains a valid source ID and evidence metadata.
8. A stale, blocked, failed, unreviewed, or unsafe artifact cannot be used to create an order.
9. Order creation always passes the existing server-side order guard and idempotency path.
10. Safety overrides require authenticated actor identity and a reason; agent policy can never auto-override them.

## 5. Canonical workspace model

Replace the implicit step machine with versioned artifacts. A simplified shape is:

```json
{
  "workspace_id": "cw_...",
  "session_id": "sess_...",
  "revision": 18,
  "mode": "copilot",
  "approval_policy": "critical_only",
  "artifacts": {
    "brief": {"status": "approved", "revision": 3, "value": {}},
    "strategy": {"status": "approved", "revision": 7, "value": {}},
    "audience": {"status": "approved", "revision": 9, "value": {}},
    "targeting": {"status": "approved", "revision": 10, "value": {}},
    "creative": {"status": "needs_review", "revision": 12, "value": {}},
    "placements": {"status": "stale", "revision": 13, "value": {}},
    "assignments": {"status": "blocked", "revision": 14, "value": {}},
    "forecast": {"status": "stale", "revision": 15, "value": {}},
    "order_draft": {"status": "blocked", "revision": 16, "value": {}},
    "order": {"status": "missing", "revision": 0, "value": null},
    "report": {"status": "missing", "revision": 0, "value": null}
  }
}
```

Allowed artifact statuses:

`missing`, `draft`, `proposed`, `approved`, `running`, `completed`, `stale`, `needs_review`, `blocked`, `failed`, `cancelled`.

The existing React steps remain useful views over these artifacts. They no longer define what the agent is allowed to reason about.

## 6. Dependency graph and non-linear behavior

Use a dependency graph rather than resetting every later tab:

```text
brief
  |-- strategy
  |     |-- audience -- targeting --+
  |     |-- placements --------------+-- forecast -- order_draft -- order -- report
  |     +-- creative_brief            |
  |                                  |
creative_files -- creative_verdict -- assignments --+
placements --------------------------+
```

Example invalidation rules:

| Change | Mark stale or recompute | Preserve |
|---|---|---|
| Brand/message | strategy, creative verdict, forecast, order draft | uploaded source files |
| Objective/KPI | strategy, audience, targeting, placements, forecast, order draft | unrelated file uploads |
| Budget | strategy, placements, forecast, order draft | audience when still valid, creatives |
| Dates | conflicts, placements, forecast, order draft | audience, targeting, creative analysis |
| Audience selection | targeting, forecast, order draft | creative analysis, placements if policy permits |
| Creative file | creative verdict, assignments, order draft | approved brief, audience, targeting |
| Zone selection | assignments, forecast, order draft | brief, audience, creative verdict |

The dependency engine must distinguish:

- **Invalid** — cannot be reused.
- **Stale** — may be displayed but cannot be launched until recomputed or explicitly revalidated.
- **Unaffected** — retain approval and evidence.

This is how users can work in a non-linear order without corrupting the campaign.

## 7. Mutation protocol for freeform chat

### 7.1 Structured intent

The first graph node classifies the turn into a strict schema:

```text
answer | inspect | propose_change | approve | reject | execute | cancel | resume | navigate
```

Keyword intercepts may remain as latency optimizations for unambiguous commands, but schema classification and proposal IDs are the source of truth. “Đồng ý” applies only to the proposal explicitly visible and pending for that session; negated or ambiguous confirmation asks a short clarification.

### 7.2 Typed workspace commands

Replace unrestricted `update_workspace(field, value)` with whitelisted commands such as:

- `set_brief_fields`
- `select_audience_segments`
- `set_targeting_rules`
- `attach_creative`
- `select_placements`
- `set_assignments`
- `request_recompute`
- `approve_artifact`
- `reject_proposal`

Each command has a Pydantic schema and domain validation. Segment IDs, zone IDs, creative analysis IDs, dates, budgets, and enum values are checked against authoritative sources.

### 7.3 Proposal lifecycle

```text
LLM intent and typed command
        -> deterministic validation
        -> impact preview
        -> durable proposal with proposal_id and base_revision
        -> user/policy approval
        -> atomic commit
        -> workspace revision increment
        -> dependency invalidation events
        -> frontend rehydrate/patch
```

The response should show the exact changes and consequences, for example: “Budget 25M → 40M; placements and forecast will be recalculated; audience and creative remain approved.”

### 7.4 State synchronization

- Add `GET /api/workspaces/{id}` for hydration.
- Add `POST /api/workspaces/{id}/proposals` and approve/reject endpoints.
- Add an SSE event stream for workspace patches, task progress, and approvals.
- Frontend requests send `workspace_id` and `workspace_revision`, not a full authoritative workspace copy.
- Keep the current compact snapshot only during migration and compare it against the server revision.

## 8. Durable Autopilot run engine

### 8.1 Run model

Create durable `agent_runs` and `agent_tasks` records:

```json
{
  "run_id": "run_...",
  "workspace_id": "cw_...",
  "plan_revision": 4,
  "status": "waiting_for_approval",
  "approval_policy": "critical_only",
  "current_task_id": "creative_review",
  "started_by": "user_...",
  "lease_owner": null,
  "cancel_requested": false,
  "created_at": "...",
  "updated_at": "..."
}
```

Task records include inputs revision, dependencies, attempt count, status, timestamps, evidence, result artifact revision, error classification, and whether approval is required.

### 8.2 Standard campaign plan

The planner selects and parameterizes capabilities, but it cannot invent tools. The standard graph is:

1. `normalize_brief`
2. `validate_brief`
3. `request_missing_information` when blocking fields are absent
4. `generate_strategy_options`
5. `select_strategy` through approval policy
6. `retrieve_and_rank_audience`
7. `derive_targeting_and_exclusions`
8. `ingest_or_generate_creatives`
9. `analyze_creatives`
10. `rank_available_placements`
11. `assign_creatives_to_placements`
12. `forecast_reach_cost_and_risk`
13. `build_order_draft`
14. `run_order_guard`
15. `request_launch_approval`
16. `create_order_idempotently`
17. `verify_order`
18. `create_setup_report`
19. `schedule_or_wait_for_performance_report`

Independent tasks may run in parallel after brief/strategy approval. Every task writes a typed artifact, not prose that another task must reinterpret.

### 8.3 Approval policy

Policy is data, not a prompt sentence. It defines:

- Which artifact types may be auto-approved.
- Minimum confidence and quality thresholds.
- Maximum budget and allowed variance.
- Allowed dates, channels, geographies, and targeting categories.
- Whether creative generation is allowed.
- Whether low-confidence results must pause.
- Explicitly forbidden actions: safety override and final order creation without launch approval.

The recommended `critical_only` policy pauses for:

- Ambiguous or incomplete brief.
- Strategy selection when options differ materially.
- Any creative `needs_review` result.
- Policy, compliance, or targeting exclusion warning.
- Forecast outside budget/KPI tolerance.
- Final order launch.

### 8.4 Replanning

When the user changes requirements during a run:

1. Pause scheduling new tasks.
2. Commit the approved workspace change.
3. Compute affected artifacts from the dependency graph.
4. Cancel queued affected tasks; let safe in-flight reads finish but discard results based on stale revisions.
5. Produce a plan diff showing removed, reused, and rerun tasks.
6. Resume after approval if the policy requires it.

Every task must compare its input revisions before committing output. This prevents a slow response from overwriting newer user changes.

### 8.5 Failure and recovery

- Use bounded retries by error class, not blind retries.
- Provider timeout may retry or use an approved fallback; validation and safety failures do not retry unchanged input.
- Workers claim tasks with leases. Expired leases return tasks to queued state.
- Restart reconstructs the run from MongoDB and resumes from the latest valid artifacts.
- A blocked run asks one actionable question and remains resumable.
- Cancel stops future work and preserves completed artifacts.
- Critic unavailability may degrade advisory explanation, but never fail open for safety, approval, order guard, or launch.

## 9. Tool boundaries

The model may plan only from a capability registry. Suggested capabilities:

| Capability | Side effect | Approval |
|---|---|---|
| Read workspace/catalog/order/report | None | Never |
| RAG audience recommendation | Writes draft artifact | Policy |
| Targeting derivation | Writes draft artifact | Policy |
| Creative generation | Creates file | Policy/usage limit |
| VLM creative analysis | Writes verdict | Never; result may require human |
| Zone ranking/conflict check | Writes draft artifact | Policy |
| Forecast/simulation | Writes draft artifact | Policy |
| Commit workspace proposal | Mutates workspace | User or policy |
| Override creative verdict | Safety-sensitive | Authenticated human only |
| Create order | Irreversible/business side effect | Explicit launch approval |
| Send email/publish/report delivery | External side effect | Explicit approval |

Executor nodes call existing deterministic handlers and validators where possible. The migration should wrap proven functions rather than rewrite them in prompts.

## 10. UI design

Add an opening experience selector before the workspace initializes. The traditional card enters the existing guided UI; the Autopilot card enters the brief intake and run UI.

For Autopilot, add a run panel above or beside the workspace:

- Run name and status.
- Approval policy selector before start.
- Plan checklist with task status and duration.
- Current task, concise rationale, evidence count, and trace ID.
- Pause, resume, cancel, and review buttons.
- Proposal diff with affected artifacts.
- “Why did the agent choose this?” evidence drawer.
- “Replan required” banner after a non-linear change.
- Final launch card separated visually from ordinary approvals.

In Traditional Guided Workflow, the existing five-step tabs remain the primary navigation. In Campaign Autopilot, they become artifact inspection views beneath the run plan. Artifact status controls whether a tab is editable, stale, blocked, approved, or ready—not its numeric position.

## 11. Storage and migration

Recommended collections:

- `campaign_workspaces` — canonical versioned artifact state.
- `workspace_events` — append-only audit log.
- `workspace_proposals` — proposal, impact, approval, and rejection records.
- `agent_runs` — durable run-level state.
- `agent_tasks` — durable task execution and evidence.
- Existing `creative_intel_jobs`, graph checkpoints, orders, and logs remain.

Migration sequence:

1. Introduce the workspace service while continuing to mirror `agent_sessions.form_state`.
2. Make all deterministic form commits pass through the workspace service.
3. Switch freeform proposals to workspace commands.
4. Hydrate the frontend from the canonical workspace.
5. Remove frontend-authoritative writes.
6. Migrate Auto mode to durable run/task records.
7. Retire mirrored `form_state` after compatibility tests and a rollback window.

## 12. Implementation slices

### M4.1 — Transactional workspace foundation

- Define artifact schemas, revisions, statuses, and dependency rules.
- Implement atomic proposal/approve/reject/commit with optimistic concurrency.
- Route current buttons and handlers through the workspace service.
- Add audit events and rehydration API.
- Preserve legacy flow behind a feature flag.

Exit: no stale client can silently overwrite a newer workspace; existing guided flow still passes.

### M4.2 — Reliable freeform Copilot

- Add structured intent and typed workspace commands.
- Resolve confirmation by proposal ID instead of global keyword state.
- Make context selection artifact-aware and grounded.
- Persist all visible/proactive messages and decisions.
- Add Vietnamese multi-turn regression set.

Exit: chat can inspect and modify every supported artifact through validated proposals with zero unauthorized mutation in tests.

### M4.3 — Non-linear orchestration

- Add dependency invalidation and stale-state UI.
- Support edit, jump, partial recompute, and revalidation from any workspace view.
- Reject late task results produced from stale revisions.
- Add plan diff and reuse evidence.

Exit: all defined non-linear scenarios finish without full reset or inconsistent order draft.

### M4.4 — Durable Campaign Autopilot

- Add the opening Guided Workflow versus Campaign Autopilot selector and persist `experience_mode`.
- Replace phrase-only Auto mode with an explicit Autopilot intake/start action and API.
- Add durable run/task store, worker leases, pause/resume/cancel, and SSE progress.
- Implement the standard campaign capability graph.
- Add approval policies and interrupt/resume checkpoints.
- Integrate RAG, creative intelligence, zone ranking, forecast, order guard, and idempotent create.

Exit: one brief can produce an order-ready draft after restart, then create exactly one order after final approval.

### M4.5 — Agentic UI and observability

- Add plan/progress/review UI and evidence drawers.
- Trace every run/task/proposal with run, workspace, artifact, and revision IDs.
- Add latency, retry, blocked-time, approval, replan, stale-result, and task-success metrics.

Exit: a judge can understand what the agent is doing and why without opening server logs.

### M4.6 — Evaluation and release

- Run unit, state-transition, multi-turn, non-linear, recovery, concurrency, security, and full campaign evals.
- Complete a one-hour soak and five consecutive demo rehearsals.
- Keep `USE_LANGGRAPH_FREEFORM` and Autopilot flags independently reversible until gates pass.

## 13. Required evaluation suites

### Freeform Copilot

At least 60 Vietnamese multi-turn scenarios covering:

- Paraphrased edits and explanations.
- Ambiguous and negated confirmation.
- Multiple pending proposals.
- Stale browser revision.
- Invalid segment/zone IDs.
- Cross-step changes and downstream impact.
- Prompt injection and attempts to bypass approval.
- Restart between proposal and approval.

Targets:

- 100% correct artifact selected for mutation.
- 0 unauthorized mutations.
- 0 stale overwrite or cross-session leakage.
- At least 95% correct proposed values on reviewed scenarios.
- 100% explicit impact preview for locked/approved dependent artifacts.

### Non-linear workflow

At least 30 scenarios such as:

- Upload creative before completing audience.
- Change budget after placement selection.
- Change dates while creative analysis is running.
- Remove an audience after a draft order exists.
- Return to an approved brief and change only brand messaging.
- Cancel, restart, and resume from a different browser session.

Targets:

- 100% correct invalidation set.
- 100% unaffected-artifact reuse.
- 0 stale artifact accepted by order guard.

### Autopilot

At least 20 full campaign briefs plus failure drills:

- Missing brief fields.
- Qdrant unavailable.
- Model timeout or malformed structured output.
- Unsafe or low-confidence creative.
- Zone conflict introduced mid-run.
- Restart during each major task class.
- User edit while a task is in flight.
- Duplicate launch approval/retry.

Targets:

- At least 90% order-ready draft completion on valid briefs.
- 100% pause on required review conditions.
- 100% restart recovery without duplicate side effects.
- Exactly one order for repeated approval with the same idempotency key.
- 0 launch without explicit final approval.

## 14. Work suitable for the secondary model

The secondary model may generate candidate test data, but it must not define production behavior. Suitable delegated work:

- Vietnamese paraphrase variations for intent scenarios.
- Candidate nonlinear briefs and edge cases.
- Candidate expected artifact changes using a provided template.
- Candidate creative safety descriptions and report questions.

Human/Codex review must validate IDs, expected invalidation, approval requirements, and final labels before these enter release gates.

## 15. Explicit non-goals

- No unrestricted model-generated code execution.
- No model-created tool names or arbitrary HTTP requests.
- No hidden chain-of-thought display.
- No auto-override of creative safety.
- No silent order creation or external messaging.
- No fabricated performance report when real data is unavailable.
- No multi-agent architecture merely for presentation; planner, executor, critic, and specialist boundaries must correspond to measurable responsibilities.
