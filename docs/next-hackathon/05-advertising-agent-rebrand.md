# Advertising Agent — Product Identity Revamp

## 1. Product decision

Rename the user-facing product to **Advertising Agent** and replace the current green visual theme with a blue, friendly, conversational design inspired by the familiarity of Zalo.

This is visual and product-language inspiration, not an attempt to copy Zalo's logo, proprietary assets, or exact interface. Advertising Agent must retain its own identity.

## 2. Rebrand boundaries

Change in this workstream:

- Product name shown to users.
- Browser title, page metadata, PWA metadata, loading screen, empty states, welcome message, and exported report headers.
- Primary color system, chat surfaces, navigation, buttons, cards, status treatments, icons, and illustrations.
- Copy tone and product terminology.
- Screenshots, demo material, and hackathon presentation assets.

Do not rename in the first pass:

- API routes such as `/api/agent/*`.
- Docker service names.
- MongoDB collection names.
- Environment variable names.
- Internal package/module names.
- Existing campaign and order identifiers.

Keeping internal identifiers stable makes the rebrand low-risk. Internal cleanup can happen later as a separate migration if it creates real value.

## 3. Visual direction

The intended feeling is:

- Familiar and approachable like a modern Vietnamese communication product.
- Blue-first, bright, clean, and trustworthy.
- Conversation-led rather than dashboard-heavy.
- Rounded and friendly without looking childish.
- Calm enough for campaign and budget decisions.

Avoid:

- Making every element blue.
- Copying Zalo's logo, illustrations, or screen layouts.
- Excessive gradients, glass effects, or decorative animation.
- Removing semantic colors from warnings, failures, safety review, and success.

## 4. Design tokens

Create semantic CSS variables/Tailwind tokens rather than replacing hex values component by component.

Suggested starting palette:

| Token | Value | Use |
|---|---:|---|
| `brand-primary` | `#0068FF` | Main actions, active navigation, links |
| `brand-primary-hover` | `#0057D9` | Hover/pressed state |
| `brand-primary-soft` | `#EAF3FF` | Selected rows, agent bubbles, subtle highlights |
| `brand-primary-border` | `#B8D6FF` | Selected and focused borders |
| `surface-app` | `#F4F7FB` | Application background |
| `surface-card` | `#FFFFFF` | Cards and workspace panels |
| `text-primary` | `#132238` | Main copy |
| `text-secondary` | `#607087` | Supporting copy |
| `border-default` | `#DCE5F0` | Neutral dividers and input borders |

Retain semantic colors:

- Green only for completed/success states.
- Amber for warning, waiting, and degraded states.
- Red for danger, rejection, blocked safety, and destructive actions.
- Purple or cyan may distinguish AI reasoning/evidence, but must remain secondary to the primary blue.

All text and interactive states must meet WCAG AA contrast. Focus rings must remain visible against white, pale blue, and dark surfaces.

## 5. Component treatment

### Opening experience selector

- Advertising Agent wordmark and short Vietnamese product statement.
- Two large choice cards: Traditional Guided Workflow and Campaign Autopilot.
- Use blue selection/focus treatment and a concise comparison of control, automation, and approvals.
- Do not visually pressure users toward Autopilot; mark it as recommended only when appropriate.

### Chat

- User messages: primary blue bubble with white text.
- Agent messages: white or pale-blue surface with dark text.
- Tool progress and evidence: compact blue-accent cards.
- Approval requests: strong border and explicit action hierarchy.
- Safety warnings preserve amber/red instead of inheriting blue.

### Workspace

- White cards on a cool light-gray/blue background.
- Blue active tabs, focus states, selected audiences, and selected zones.
- Completed items remain green; stale and review-required items use semantic warning colors.
- Rounded controls and compact spacing should feel conversational while retaining dense campaign information.

### Autopilot run panel

- Blue progress line and active-task indicator.
- Clear neutral states for queued work.
- Green only after verified completion.
- Amber for paused/review and red for blocked/failed.
- Final launch approval must look more consequential than ordinary task approvals.

## 6. Product language

Primary user-facing name: **Advertising Agent**.

Suggested Vietnamese welcome copy:

> Xin chào! Tôi là Advertising Agent. Bạn có thể thiết lập chiến dịch theo từng bước hoặc giao brief để tôi tự xây dựng một bản campaign hoàn chỉnh và chờ bạn duyệt.

Tone:

- Clear, helpful, concise Vietnamese.
- Use “bạn” consistently unless a hackathon audience explicitly requires another form of address.
- Explain actions and consequences directly.
- Avoid pretending the agent completed work that is still queued or awaiting review.
- Keep technical model/provider names out of ordinary user-facing copy.

## 7. Implementation sequence

1. Inventory all user-facing instances of the old product name and green color literals.
2. Add centralized design tokens and map existing components to semantic tokens.
3. Rename user-facing product metadata and core copy to Advertising Agent.
4. Restyle application shell, top bar, navigation, chat, workspace controls, and dialogs.
5. Restyle Guided Workflow, Campaign Autopilot, creative review, reports, and result pages.
6. Verify loading, empty, success, warning, blocked, stale, error, and offline states.
7. Update demo scripts, screenshots, exported logs/reports, and presentation material.
8. Remove obsolete green-theme CSS only after visual regression passes.

## 8. Acceptance criteria

- No old user-facing product name remains in the application or demo assets.
- No primary green branding remains; green appears only as a semantic success color.
- Guided Workflow and Campaign Autopilot share one coherent visual system.
- Every major screen works at desktop demo width and a narrow/mobile viewport.
- Keyboard focus, hover, disabled, loading, warning, error, and selected states are visually distinct.
- WCAG AA contrast passes for core text and controls.
- Frontend production build and browser smoke flow pass.
- Before/after screenshots exist for the opening selector, chat/workspace, creative review, Autopilot progress, and final result.
- Internal APIs, service names, database collections, and order behavior remain unchanged.

## 9. Cut line

If time is limited, complete these first:

1. Product name and metadata.
2. Central design tokens.
3. Application shell, opening selector, chat, primary buttons, tabs, and workspace cards.
4. Autopilot progress/review states.
5. Demo screenshots.

Custom illustrations, advanced motion, and an internal identifier rename are optional and must not delay product reliability work.
