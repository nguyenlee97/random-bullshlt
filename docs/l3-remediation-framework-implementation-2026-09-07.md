# L3 remediation framework — M0 to M3

## Delivered boundary

L3 now separates three proposal kinds:

- `executable_action`: an owner-approved mutation with a registered executor.
- `operator_workflow`: instructions and audited operator acknowledgement/steps.
- `engineering_escalation`: evidence package and external engineering steps; it
  never creates a coding agent, edits source, commits, or deploys.

The action registry is server-owned. L2 contributes only a bounded cause and
evidence bundle. A client can select only a candidate returned for that exact
incident, dataset revision, and policy version.

`restore_config_revision` remains the only production executor. Creative,
placement, click-surface, and report-pipeline actions are workflows or
escalations, not hidden production mutations.

## Scenario Lab recovery

Synthetic recovery uses a separate internal executor and an allowlisted pair of
`actionId` plus `interventionType`. It creates an immutable `recovery` dataset
revision with:

- parent revision;
- proposal and action identity;
- intervention and requested synthetic outcome;
- rebuilt six-report analysis snapshot.

The parent scenario is never overwritten. Evaluation runs against the child
revision. If evaluation is temporarily unavailable after publication, the
proposal remains `ready_to_verify` and retries verification without applying a
second recovery revision.

Allowlisted interventions are:

- `restore_delivery`
- `restore_click_measurement`
- `replace_creative_fixture`
- `remove_click_overlay_fixture`
- `restore_config_fixture`
- `switch_placement_fixture`
- `backfill_attribution_fixture`

Scenario labels and expected answers never enter L2 prompts. The active dataset
kind establishes only that a Lab executor is eligible; action selection still
comes from current L2 evidence. When L2 is ambiguous, the server can offer the
non-causal `hold_optimization_and_recheck` workflow and a synthetic test
intervention, but never a production executor.

## State and safety contracts

- Executable: `awaiting_approval -> executing -> resolved | rolled_back | failed`.
- Workflow/escalation: `awaiting_acknowledgement -> waiting_operator |
  waiting_external -> ready_to_verify`.
- Scenario Lab: `ready_to_verify -> executing -> resolved | ineffective`, with
  a retryable return to `ready_to_verify` when only Evaluation fails.
- Every transition is ownership-scoped, version-checked, audited, and bound to
  current policy/evidence before acknowledgement.
- Durable storage is required before any production or Lab dataset mutation.
- Web exposes candidate selection, exact-code production approval,
  acknowledgement, workflow steps, and Lab apply/verify.
- Zalo creates the same server-owned proposal. Exact approval syntax remains
  executable-only; workflows/escalations deep-link to the web control plane.

## Runtime flags

All proposal/execution boundaries remain explicit:

```text
EVALUATION_L3_PROPOSALS_ENABLED=false
EVALUATION_L3_EXECUTION_ENABLED=false
EVALUATION_L3_LAB_ENABLED=false
EVALUATION_L3_WORKFLOWS_ENABLED=true
EVALUATION_L3_ESCALATIONS_ENABLED=true
EVALUATION_L3_ACTION_ALLOWLIST=
```

An empty action allowlist uses the registry defaults. A non-empty comma-separated
list narrows available actions; it never creates a new action or executor.

## Intentionally not implemented

- No production creative replacement.
- No production placement/budget switch.
- No source-code editing or automated deploy from an escalation.
- No claim that a completed operator checklist proves KPI recovery.
- Production verification for non-mutating workflows remains a later milestone;
  M3 stops at `ready_to_verify` outside Scenario Lab.
