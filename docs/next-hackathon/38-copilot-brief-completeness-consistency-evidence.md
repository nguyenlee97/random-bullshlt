# Campaign Copilot Brief completeness consistency evidence

Date: 2026-07-19

Branch: `revamp/next-hackathon`

Production build: `2026-07-19.7`

## Reported behavior

Repeated fresh Copilot runs against the same complete factual request could
either propose a Brief or ask for objective, KPI or audience. One rare run
returned only a generic clarification sentence and left the workspace at
revision zero.

The production trace for that rare run returned HTTP 200 and recorded a valid
structured model call with `action=ask_clarification`, `has_brief=false`. It was
not an order guard, workspace mutation or Autopilot failure. MiniMax returned an
empty `missing_fields` list, so the earlier renderer had no actionable question
to expand.

## Authoritative policy

Campaign Copilot now separates inputs into two classes:

- Hard facts: brand, budget, start date and end date/duration. The Agent must
  ask when one of these is absent and must never invent it.
- Advisory decisions: objective, KPI, notes, audience and geo. These never
  block initial intake. The Agent proposes reasonable values in a durable,
  editable Brief draft that still requires operator approval.

The `BriefTurn` schema—not a prompt-only instruction—enforces this boundary.
`ask_clarification` must contain at least one hard missing field, advisory field
names are rejected by validation, and other actions cannot carry
`missing_fields`. Invalid provider output uses the existing structured-output
repair retry and fails closed if the retry remains invalid.

Non-question campaign messages use a narrower `BriefIntakeTurn` schema that
allows only `propose_brief` or `ask_clarification`. The general `answer` action
remains available for explicit explanatory questions such as “Objective nào
phù hợp?” or “Budget tối thiểu là bao nhiêu?”. This prevents an incomplete
campaign statement from being acknowledged as prose without an actionable
next state.

## Verification

### Focused and full tests

- Brief collector and legacy approval tests: **21 passed**.
- Full Agent suite: **312 passed**, 0 failed, 2 existing warnings.
- New coverage rejects empty clarifications, advisory-field clarifications and
  `missing_fields` on non-clarification actions while preserving explicit hard
  fact questions.

### Configured-model consistency probe

The exact reported input was submitted to the configured MiniMax structured
collector ten times with bounded concurrency:

`chiến dịch world cup của cocacola, bắt đầu từ ngày 18/7/2026, budget 1 tỉ, chạy 1 tuần`

Result: **10/10 `propose_brief`**, 0 clarifications and 0 provider/schema errors.
Every draft used objective `awareness`, budget `1000` million VND and dates
`2026-07-18` through `2026-07-24`.

### Production acceptance

- `/api/version` returned `2026-07-19.7` with
  `guided-deterministic-brief-completeness`.
- `/ready` reported Mongo, backend, creative worker, Autopilot worker, Zalo
  worker and Zalo OpenAI ready.
- Five additional calls against the deployed collector returned **5/5**
  `propose_brief` for the exact reported input with the same objective, budget
  and date values.
- A name-only campaign statement asked for budget and dates; name plus budget
  asked only for dates; budget plus dates asked only for brand.
- “Objective nào phù hợp với tôi?” remained an ordinary `answer`, proving that
  explanatory Brief questions were not converted into campaign intake.

These isolated model probes did not create a workspace proposal, approve a
Brief or create an order.

## Compatibility and rollback

No API, Mongo model, stored workspace, Autopilot intake, ownership or order
behavior changes. Existing conversations and proposals remain readable. The
change affects only validation of newly generated Copilot Brief turns and is
rollback-safe by restoring the previous Agent runtime files.

Rollback archive:

- `/var/backups/agent-api-brief-consistency-20260719-231006.tar.gz`
