# Advertising Agent Design Sync Notes

- Source shape: package. Repository has no Storybook or stories.
- Source package: `agent_frontend`; build with `npm --prefix agent_frontend run build`.
- Claude Design target: `Advertising Agent — Design System` (`6fc0da6a-eb91-4b66-ae59-b69f457805cb`).
- `agent_frontend/design-system-entry.jsx` and `.d.ts` are sync-only public exports for the real application components; they do not replace the runtime app entry.
- The compiled CSS filename under `agent_frontend/dist/assets/` is content-hashed. If the Vite build changes it, update `cssEntry` in `.design-sync/config.json` before syncing.
- Inter is expected by the product but no local font files are shipped. On 2026-07-20, the user explicitly chose to accept the documented `system-ui, -apple-system, sans-serif` fallback instead of bundling or remotely loading Inter in Claude Design.
- Landing-page redesign requirements are copied as guidelines from `docs/advertising-agent-landing-redesign-handoff.md`.

- Driver invocation (repo tự thân, không có `node_modules/agent-frontend`): phải truyền `--entry ./design-system-entry.jsx` (package-relative), nếu không build fail ENOENT tại `lib/dts.mjs projectFor`. Full lệnh: `node .ds-sync/resync.mjs --config .design-sync/config.json --node-modules agent_frontend/node_modules --entry ./design-system-entry.jsx --out ./ds-bundle [--remote .design-sync/.cache/remote-sync.json]`.
- 2026-07-23: landing page tách thành block exports trong `PublicLanding.jsx` (LandingNav/Hero/Pain/HowItWorks/Modes/Proof/FinalCta/Footer), nhóm `Landing` qua `docsMap` trỏ vào `docs/design-sync/landing/*.md` (docs/ bị gitignore — giữ file cẩn thận). Preview wrapper: block sáng dùng nền `#eef5ff` KHÔNG kèm class `.public-landing-v2` (class đó vẽ gradient tối 100vh đè lên); block tối (Nav/Hero) dùng class + nền `#020817`. Block render ngoài PublicLanding tự bật scroll-reveal qua `useStandaloneReveal` (check `closest('.public-landing-v2')`).
- Owner direction 2026-07-23 (xem cuối `docs/advertising-agent-landing-redesign-handoff.md`): thích headline "Make your campaign move."; nav cần links tới mockup Ad Server/DMP/Analytics (prop `links`); owner tự viết copy theo pain points; CTA một động từ duy nhất.
- Playwright chromium đã có sẵn trong `%LOCALAPPDATA%\ms-playwright` (chromium-1208/1223/1228) — không cần cài lại.

- Grade files `.design-sync/.cache/review/*.grade.json` phải là UTF-8 KHÔNG BOM — PowerShell 5.1 `Out-File -Encoding utf8` chèn BOM làm capture bỏ qua grade (0 carried forward). Ghi bằng node `fs.writeFileSync`.
- Ảnh public (`mascot`, `autopilot-strategy`) được import qua bundler trong `PublicLanding.jsx` (import từ `../../public/...`) để esbuild nhúng data URI vào `_ds_bundle.js` — URL tuyệt đối `/brand/...` không resolve trong Claude Design. Test anchor regex vẫn khớp nhờ chuỗi `/brand/advertising-agent-mascot.png` nằm trong đường dẫn import.
- `SplitDivider` root có `md:hidden` — viewport capture phải <768px (đang đặt 420x220), nếu không render rỗng.
- `AutopilotPanel`/`AdImageGenerator` preview stub `window.fetch` (trả `{}`) vì component gọi API khi mount; không có stub sẽ dính pageerror "Failed to fetch".
- Tailwind purge: KHÔNG có `bg-primary`/`text-primary-foreground`/`bg-accent` trong CSS compiled; brand blue là scale `bg-brand-50…600`. Conventions.md đã sửa theo.

## Known render warns

- `[FONT_MISSING] "Inter"` — user đã chấp thuận fallback system-ui (2026-07-20), giữ nguyên.

## Re-sync risks

- Vite may produce a new hashed CSS filename after source changes; stale `cssEntry` causes unstyled previews.
- Several product components depend on API/state-rich props. Authored previews must remain fictional and deterministic, with no network access or private campaign data.
- Overlay components need single-card viewports and static open-state fixtures.
- Report and chart previews must keep synthetic/showcase disclosures visible.
- Source `docs/` is ignored by the repository's current `.gitignore`; guideline edits may not appear in normal git status.
- Light mode is the only verified theme; do not imply a complete dark theme on re-sync.
