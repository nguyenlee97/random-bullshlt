# Advertising Agent — build conventions

This library is the real UI of a Vietnamese-language advertising campaign agent (product copy is Vietnamese; keep it Vietnamese unless asked otherwise).

## Setup

- No provider wrapper is required — components style themselves from the compiled stylesheet.
- Font is `Inter, system-ui, sans-serif`; it is inherited from context, so set `fontFamily: 'Inter, system-ui, sans-serif'` on your outermost container.
- App components assume a light app shell; `Landing*` components have fixed planes (see below).

## Styling idiom

Two coexisting idioms — match the component you're composing around:

1. **App/product components** (buttons, cards, workspace, steps): Tailwind utilities on shadcn/ui-style primitives. Semantic tokens: `bg-background`, `text-foreground`, `bg-card`, `text-muted-foreground`, `border-border`, `bg-secondary`, `bg-destructive`, rounding from `--radius: 0.625rem`. Brand blue (≈ #0068ff) is a `brand-*` scale: `bg-brand-50…600`, `border-brand-100…500`, `ring-brand-100…400`. Prefer component variants over raw color classes for controls — `Button` variants: `default | destructive | outline | secondary | ghost | link | amber | brand-outline`; sizes `default | sm | lg | xl | icon`. `Badge` variants include `green | amber | blue | violet | red | muted`.
2. **Landing blocks** (`Landing*`, `PublicLanding`): hand-written CSS classes (`landing-*`, `campaign-*`, `truth-*`, `mode-*`) shipped in the stylesheet. Do NOT restyle their internals with Tailwind; place them on the correct plane instead — dark plane `#020817` for `LandingNav`/`LandingHero` (wrap those two in `className="public-landing-v2"` to get the page gradient), light plane `#eef5ff` for `LandingPain`/`LandingHowItWorks`/`LandingModes`/`LandingProof` (no `public-landing-v2` class — it paints a dark gradient), and `LandingFinalCta`/`LandingFooter` carry their own dark backgrounds.

## Where the truth lives

- Compiled CSS (tokens + all `landing-*` classes): `styles.css` → `_ds_bundle.css` import closure.
- Per-component API: `components/<group>/<Name>/<Name>.d.ts`; usage notes: `<Name>.prompt.md`.
- Landing design direction (block-per-job, headline variants, nav ecosystem links): `guidelines/advertising-agent-landing-redesign-handoff.md` — the "Owner Direction — 2026-07-23" section is authoritative.

## Idiomatic build snippet

```jsx
<div style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
  <div className="public-landing-v2" style={{ background: '#020817', color: '#fff' }}>
    <LandingNav onEnterAgent={() => {}} links={[{ label: 'Ad Server', href: '#' }, { label: 'DMP', href: '#' }]} />
    <LandingHero title={<>Make your<br /><em>campaign move.</em></>} onEnterAgent={() => {}} onOpenDemo={() => {}} />
  </div>
  <div style={{ background: '#eef5ff' }}>
    <LandingPain />
  </div>
</div>
```

Gotchas: `Landing*` blocks self-activate their scroll-reveal animations when rendered standalone — no observer setup needed. `onOpenDemo` receives only `'copilot' | 'autopilot'`. Report/chart components must keep their synthetic-data disclosures visible.
