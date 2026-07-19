# Campaign Copilot model-led Brief delegation evidence

Date: 2026-07-19

Branch: `revamp/next-hackathon`

Production build: `2026-07-19.9`

## Correct product behavior

Campaign Copilot asks for missing Brief fields by default. It may propose
missing objective, KPI and audience/geo notes only when the user naturally
delegates those decisions. Brand, budget and schedule remain hard facts that
the Agent may normalize but never invent.

The browser regression showed the over-constrained build repeating the same
three questions after the user said “gợi ý giúp mình đi” twice and “sao không
gợi ý.” That behavior was safe but ignored conversational intent.

## Architecture

Two typed model responsibilities run concurrently:

1. MiniMax produces the Brief turn or reviewable proposal.
2. The configured GPT-5.4-mini critic classifies advisory-field semantics:
   - `provided_fields`: fields with actual user-supplied values;
   - `delegated_fields`: fields the user authorized the Agent to fill;
   - mode: `none`, `advice_only`, or `fill_brief`.

The semantic classifier reads recent user and assistant turns. It distinguishes
“audience game thủ 18–30 tại Hà Nội” from “audience để tôi cung cấp sau,” and
distinguishes “Objective nào phù hợp?” advice from “chọn objective giúp tôi”
Brief delegation. This is a model-understood boundary, not a keyword router.

The server computes unresolved advisory fields as fields in neither the
provided nor delegated sets. A proposal remains durable, editable and
approval-gated. Classifier failure defaults to asking; it never grants
suggestion permission.

## Verification

### Automated

- Focused Brief and legacy approval tests: **26 passed**.
- Full Agent suite: **317 passed**, 0 failed, 2 existing warnings.

### Semantic classifier consistency

Five repetitions of each scenario produced identical decisions:

- Initial VNG facts: `none`, no provided/delegated advisory fields.
- “gợi ý giúp mình đi” after the questions: `fill_brief`, delegated objective,
  KPI and notes.
- KPI-only delegation: `fill_brief`, delegated KPI only.
- “Objective nào phù hợp?”: `advice_only`, no Brief delegation.
- Full browser history ending “sao không gợi ý”: `fill_brief`, delegated all
  three advisory fields.

### End-to-end configured-model behavior

- 3/3 initial requests asked exactly for objective, KPI and notes.
- 3/3 generic delegation turns created reviewable Brief proposals.
- 3/3 full browser-history turns created reviewable Brief proposals.
- KPI-only delegation asked only for objective and notes.
- The explanatory objective question remained an ordinary answer.

All generated proposals preserved VNG, budget `100` million VND and dates
`2026-07-18` through `2026-07-20`.

## Compatibility

No API, Mongo schema, workspace ownership, Autopilot intake or order behavior
changes. Existing pending proposals remain explicit user decisions. The change
affects only new Guided Copilot Brief turns.

## Production acceptance

Production was updated to build `2026-07-19.9` on 2026-07-19.

- `GET /api/version` reports `guided-model-led-brief-delegation`.
- `GET /ready` reports `status=ready`; Mongo, backend, creative worker,
  Autopilot worker, Zalo worker and Zalo OpenAI are all healthy.
- Direct deployed-model probes passed all five boundaries: initial facts ask
  for objective/KPI/notes; generic delegation proposes all three; the exact
  formerly looping browser history proposes all three; KPI-only delegation
  asks only for objective/notes; an objective advice question remains an
  answer without mutating the Brief.
- In the existing production browser conversation, a new `gợi ý giúp mình đi`
  produced a reviewable proposal instead of repeating the missing-field list.
  The proposal preserved VNG, budget `100` million VND and dates
  `2026-07-18` through `2026-07-20`, while suggesting Awareness, KPI and
  audience notes. The browser test stopped before `Đồng ý, cập nhật`, so it
  created no workspace revision, campaign or order.

## Rollback

The pre-deploy production files are archived at:

`/var/backups/agent-api-model-led-brief-20260719T165754Z.tar.gz`
