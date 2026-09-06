# Incident Q&A and Zalo namespace isolation — milestone 2

2026-08-31, local uncommitted continuation on `codex/v4-live-evaluation`.
HEAD remains `f8e4a41`; the existing no-commit V4 merge is preserved.
At this local milestone: no staging, commit, push, deployment, real model call or OA delivery test.

Deployment follow-up: [VPS acceptance on 2026-08-31](EVALUATION_VPS_ACCEPTANCE_2026-08-31.md)
records the deployed build, real Mongo/provider/HTTPS/browser results and actual
L2 quality failures. OA delivery remains unverified; L3 remains disabled.

## What changed

`agent/evaluation/questions.py` is the shared Web/Zalo read-only answer service.
It reads an owned incident's current multi-agent bundle, fixes campaign/scope,
dataset revision and policy version, and supplies only matching evidence to one
bounded structured model call. It does not expose investigation tools, campaign
creation tools, order mutation or recovery actions. It does not read a campaign
conversation or Zalo session history.

The service checks bundle/revision/policy and active report revision before every
call or cached replay, and checks again after the call. A result based on changed
data is rejected rather than published as current. Citation IDs must belong to
the supplied scope/revision. Empty citations are allowed only for an explicit
insufficient-evidence response. Partial/ambiguous investigations cannot be raised
to a supported-hypothesis assessment by the answer adapter. These checks constrain
provenance and authority; they do not prove semantic correctness of model prose.

### Persistence and limits

- Mongo `evaluation_incident_questions`, with no production in-memory fallback.
- Request identity includes channel, campaign, incident and request ID; question,
  revision, bundle and policy are fingerprint-bound. Different payload with the
  same request ID is rejected. Completed retries reuse their response.
- Atomic claim with 90-second token-fenced lease, at most two attempts per request.
  A lost lease cannot publish an answer. Provider/validation failure is explicit.
- At most 30 model-call reservations per incident/dataset revision across Web and
  Zalo, including failed calls and fresh request IDs. Not a tenant-wide daily quota.
- Question max 1,200 characters; context max 48,000 characters; model output budget
  remains 2,400 tokens with no automatic SDK retries; outer timeout 45 seconds.
- Audit retains question, response/citations, revision, bundle, policy, model,
  channel, timestamps, attempt count and sanitized failure type.
- History returns the latest 20 completed answers. This is a response limit, not
  a deletion/retention policy. Historical entries retain revision/bundle labels.

### Owned Agent API

Under `/api/agent/evaluation/campaigns/{campaign_id}/incidents/{incident_id}`:

| Endpoint | Purpose |
| --- | --- |
| `POST /questions` | Answer an explicit question with `requestId`, `expectedRevision`, `expectedBundleId` |
| `GET /questions` | Return scoped completed Q&A history |

Both routes enforce existing server-side campaign ownership before accessing Q&A.
The frontend uses the existing CSRF-aware `agentFetch` transport. No direct browser
access to internal report mutations was added. HTTP 409 means stale/conflicting
context; 403 disabled L2; 429 budget reached; 503 unavailable storage/provider.

### Web interaction

`IncidentQuestions` in Campaign Management's Live Evaluation tab displays answers,
evidence IDs/probes/sources and revision. The composer is enabled only with L2
multi-agent and an investigation bundle. A changed revision/bundle invalidates an
in-flight UI result; unchanged retries retain their request ID. Reload fetches
history from the service, and old-revision answers are labelled historical.

This is incident-grounded Q&A, not the general Campaign Agent sidebar chat. The
sidebar wording was corrected accordingly. Each question is grounded in the bundle;
prior conversational turns are not passed to the model.

### Zalo routing

1. An explicit single `INC-*` or provider reply-to an evaluation alert selects the
   namespace. `recent_incident_refs` alone never select the active topic.
2. Multiple explicit codes, or a code conflicting with provider reply-to, ask for
   clarification before reading or mutating an incident.
3. Menu commands are full-string matches, not prefix matches. `4 INC-ABC123` can
   dismiss; `4 INC-ABC123 là gì?` is a read-only question and cannot dismiss.
4. Free-form questions use the same Q&A service after ownership resolution. The
   provider event ID supplies a stable request key; no shared campaign pending
   action is created. The response includes a bounded excerpt/citation list and
   points to full Web Q&A history.
5. Incident routing now happens **before** either campaign message history and
   before rolling a campaign chat session. Incident questions/replies therefore
   cannot enter campaign tool context or subsequent campaign summaries, nor clear
   a pending approval solely by rolling its session. Both legacy and OpenAI OA
   handlers support this interception; ordinary legacy behavior is preserved.
6. Explicit common switches (`FAQ`, `Xem report`, `Tạo campaign mới`, generic
   `Xác nhận`) without an incident code continue through the campaign flow, even
   if the message quotes an alert. This is bounded deterministic routing, not a
   comprehensive multilingual intent classifier.

Unscoped natural follow-ups are deliberately not inferred from the latest alert.
Follow-ups must include the incident code or reply to its alert. Q&A reply messages
do not yet carry a new provider correlation namespace; the original alert or code
is the supported anchor. General campaign chat history is not retroactively
rewritten; this change isolates new incident turns only.

## Verification

- New tests cover stale data before/after calls, invalid/foreign citations, tool
  action rejection, ownership, replay/concurrent duplicate requests, request-payload
  conflicts, lease loss, two-attempt and 30-call limits, missing storage, partial
  assessment, ambiguous Zalo IDs, quoted-alert flow switches and both OA modes'
  campaign-history isolation.
- Agent UI tests include source contracts for revision binding, request reuse and
  stale-result suppression. These are not mounted-component tests.
- Browser check used the actual Agent UI and loopback fixture API: preview/apply
  click-overlay scenario, L1 CTR incident, specialist/coordinator results, question
  submission, two evidence citations and history restored after page reload.
  Applying revision 3 caused the existing revision-2 answer to display the
  historical-evidence warning without a page reload.
- The harness uses a **scripted model and Mongo-shaped memory adapter**. Chromium
  really observes the isolated test document. No actual provider reasoning quality,
  real Mongo concurrency, production auth/CSRF, mobile layout or OA delivery is
  claimed by this browser test. The harness must never be deployed.

Final automated validation:

- Full Agent: **762 passed, 6 failed**. The same six baseline failures remain:
  expired ZPlay brief fixture, two old mocks without `responses.parse`, undefined
  audience `proposal`, targeting reasoning order, and expired order-guard date.
- Focused evaluation/investigation/Zalo subset: **212 passed** before the final
  additional provider-retry/partial-assessment test (which passes in the full run).
- Agent UI: **204 passed** and Vite production build passed; existing >500 KB
  chunk warning remains. `git diff --check` passed.
- Backend **87 passed** and Analytics **8 passed** earlier in this turn; M2 made
  no further changes to those applications.

## Still not complete

L3 remains disabled. No approval, executor, actual remediation or verification
window was added. Baseline reset remains a Scenario Lab operation. Broader independent
evidence adapters for the older scenario presets, real-model evaluation, real Mongo
lease/concurrency tests, notification preferences/receipts, OA test-account smoke
checks, automatic monitoring enrollment, snooze/cooldown and root-incident grouping
remain separate gaps. The overall evaluation loop is not production-ready.
