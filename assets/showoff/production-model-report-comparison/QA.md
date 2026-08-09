# QA — Production Model Report Comparison

## Production model receipts

| Campaign | Provider | Model | Tool | Validation | Attempt | Generated at |
|---|---|---|---|---|---:|---|
| VoltRide | production_agent | gpt-5.4-mini | search_ad_knowledge | passed | 1 | 2026-08-08T10:01:05.708Z |
| MộcAn Dairy | production_agent | gpt-5.4-mini | search_ad_knowledge | passed | 1 | 2026-08-08T10:01:21.428Z |

The artifact stores no conversation ID, cookie, CSRF token, API key, or user credential. Temporary production conversations were deleted after generation.

## Automated checks

- Backend test suite: 69/69 passed.
- Agent report/model tests: 23/23 passed.
- Report v2 evaluation score: 100/100.
- HTML build completed from `template.html` plus embedded `report-data.json`.
- Production model output validated against allowed question IDs, finding IDs, metric definitions, and evidence contract.
- Model-supplied metric values are grounded to canonical campaign or zone evidence.
- Zone actions and Q3 evidence use cost per business outcome; CTR alone cannot select the recommended zone.

## Visual and interaction checks

- Desktop viewport: 1440 × 1000.
- Mobile viewport: 390 × 844.
- Campaign tabs switch between VoltRide and MộcAn Dairy.
- System/light/dark controls render without overlap at the mobile breakpoint.
- No browser console warnings or errors observed.
- MộcAn Q3 was expanded and verified: `zalo_retargeting_mobile`, 166 subscriptions, 89,756 VND CPL.

Screenshots:

- `images/desktop-hero.png`
- `images/mocan-dashboard-desktop.png`
- `images/mobile-top.png`
- `images/mocan-dashboard-mobile.png`

## Known assumptions and limitations

- MộcAn Dairy's “3 weeks” is represented as 2026-08-10 through 2026-08-30 for this test.
- “~5,000 lead/order” is interpreted as a combined top-funnel lead or subscription target and needs business-owner confirmation.
- MộcAn ROAS is not evaluated because recognized revenue, subscription plan value, and refund/cancellation value are missing.
- Scenario facts are deterministic decision-testing inputs, not ad-server delivery logs.
