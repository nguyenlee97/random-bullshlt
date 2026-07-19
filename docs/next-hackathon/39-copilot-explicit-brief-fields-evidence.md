# Campaign Copilot explicit Brief-field evidence

> Superseded by build `2026-07-19.9`. Product review clarified that users may
> naturally delegate missing objective, KPI and audience/geo decisions to the
> Agent. See `40-copilot-model-led-brief-delegation-evidence.md`.

Date: 2026-07-19

Branch: `revamp/next-hackathon`

Production build: `2026-07-19.8`

## Product correction

Guided Campaign Copilot must not synthesize missing Brief values. The operator
provides every field; Copilot may normalize spelling, units and an explicitly
provided duration, but it asks for missing information before creating a
reviewable proposal.

The browser-reported VNG input supplied the event, brand, budget, start date
and duration only. Build `2026-07-19.7` incorrectly proposed Awareness,
numerical KPIs, audience demographics, nationwide geo, platform assumptions
and creative formats. The workspace was still revision zero; these values came
from the pending AI proposal, not from existing workspace data.

## Enforced policy

- Brief fields: brand, objective, KPI, budget, start date, end date/duration,
  and notes containing audience plus geo/special requirements.
- `ask_clarification` must list at least one valid Brief field.
- Non-question campaign statements can only propose or clarify; ordinary Brief
  questions may still return explanatory answers.
- Server-side signal checks scan all user turns for explicit objective, KPI,
  audience/geo, brand, budget and schedule evidence.
- A model proposal is converted to clarification when objective, KPI or
  audience/geo evidence is absent.
- Fields already present in the conversation are removed from stochastic model
  clarification output so Copilot does not re-ask them.
- Only after all required information is explicitly present may the model
  create the durable proposal that the operator can approve or edit.

## Verification

### Automated

- Brief collector and legacy approval tests: **23 passed**.
- Full Agent suite: **314 passed**, 0 failed, 2 existing warnings.
- Coverage includes empty clarification rejection, all-field clarification,
  intake-only routing, false model proposal conversion, explicit-field
  proposal acceptance, explanatory questions and VNG hard-field preservation.

### Configured-model consistency

Exact reported input:

`quảng cáo chung kết thế giới liên minh huyền thoại, VNG, budget 100 triệu, 3 ngày từ 18/7/2026`

Result over ten identical fresh calls:

- **10/10** `ask_clarification`
- **10/10** exact missing set: `objective`, `kpi`, `notes`
- 0 proposals, 0 errors
- 0 runs re-asked brand, budget, start date or duration

A multi-turn completion supplied:

- Objective: Awareness
- KPI: Reach 2 million and 5 million impressions
- Audience/geo: esports gamers aged 16–35 in Hanoi and Ho Chi Minh City

The next turn produced one proposal preserving those explicit values, budget
`100` million VND and dates `2026-07-18` through `2026-07-20`.

### Production acceptance

- `/api/version` returned `2026-07-19.8` with
  `guided-explicit-brief-fields`.
- `/ready` reported Mongo, backend, creative worker, Autopilot worker, Zalo
  worker and Zalo OpenAI ready.
- Five calls against the deployed collector returned **5/5**
  `ask_clarification` with exactly `objective`, `kpi`, `notes`, no Brief and no
  errors.
- The probes called only the structured collector and did not create a
  conversation, workspace proposal, approval or order.

## Compatibility

No API, Mongo model, workspace ownership, Autopilot intake or order behavior
changes. Existing pending proposals remain explicit user decisions and are not
silently deleted or approved. The affected browser proposal must be canceled
or the campaign restarted before retesting the corrected intake policy.

Rollback archive:

- `/var/backups/agent-api-explicit-brief-20260719-233312.tar.gz`
