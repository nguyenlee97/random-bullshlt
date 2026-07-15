# Advertising Agent Rebrand — Local Completion Evidence

> Status: implementation and local verification complete on 2026-07-15.
> Final local release-candidate screenshots were captured after the performance,
> responsive and browser gates passed.

## Delivered scope

- The user-facing product identity is **Advertising Agent** in browser metadata,
  the opening selector, application shell, boot greeting, agent prompts,
  technical documentation, exported email, and generated PDF reports.
- The opening selector offers **Guided Workflow** and **Campaign Autopilot** as
  equal first-class choices, with Vietnamese descriptions and explicit launch
  approval language.
- The primary visual system uses centralized blue brand tokens based on
  `#0068FF`, with `#0057D9` for pressed/hover treatment and pale-blue surfaces.
- Green remains only for semantic success, completion, conversion, or live
  states; amber and red remain review/warning and danger colors.
- User-visible references to the legacy external platform name were replaced by
  the product-neutral label **Trình quản lý quảng cáo**. Internal routes,
  environment variables, Docker services, and database names were preserved.
- Email and PDF exports now carry the new identity and blue palette.
- Technical documentation and demo scripts now use the new product language.
- Chat log downloads now use the `advertising-agent-log-*` filename.

## Accessibility and responsive changes

- Added accessible names to mobile icon-only top-bar controls, the chat
  composer, mode choices, and Autopilot pause/resume/cancel/refresh controls.
- Added tab-list semantics and selected-state reporting to the mobile
  Chat/Workspace switcher.
- Preserved the single-pane mobile flow and desktop split-pane flow through
  explicit responsive contracts.
- Darkened muted copy and low-contrast supporting text after a computed-style
  contrast audit found two 4.43:1 selector labels and seven 4.37:1 workspace
  labels.

## Automated verification

Frontend:

```text
node --test tests
18 passed, 0 failed

vite build
2569 modules transformed with Vite 6.4.3; build passed without an oversized-chunk warning
```

The new branding regression suite checks:

- old user-facing product names do not return;
- email, PDF, and technical docs use the blue palette;
- external platform links use neutral labels;
- the two-mode selector retains responsive classes;
- mobile tabs and core icon controls retain accessible names.

Agent regression:

```text
python -m pytest tests -q
167 passed
```

## Local browser verification

The rebuilt Docker frontend at `http://localhost:5175` was exercised against
the live local agent/backend stack.

| Surface | Text/control nodes checked | WCAG AA contrast failures | Horizontal overflow | Result |
|---|---:|---:|---:|---|
| Opening mode selector | 12 | 0 | no | pass |
| Guided Workflow | 64 | 0 | no | pass |
| Campaign Autopilot | 74 | 0 | no | pass |

The browser smoke also verified:

- document title and language metadata;
- both mode cards expose descriptive accessible names;
- both modes open the expected local UI;
- the Guided greeting identifies Advertising Agent;
- Autopilot remains disabled until required brief fields exist;
- technical documentation uses the Advertising Agent title and blue tokens.

## Final screenshot evidence

- Desktop opening selector: `screenshots/01-opening-selector.png`.
- Autopilot Strategy Simulator: `screenshots/02-autopilot-strategy.png`.
- Mobile selector after scrolling to Autopilot and privacy copy: `screenshots/03-mobile-mode-selector.png`.
- At 390x844 the selector has a constrained 844-pixel scroll viewport, 1,307 pixels of reachable content and zero horizontal overflow.
