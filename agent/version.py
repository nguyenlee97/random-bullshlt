"""Build version — separate module so handlers can import it without
touching main.py (kills the main→router→boot→main circular import)."""
# ── Build version ─────────────────────────────────────────────────────────────
# Bump this manually (or via deploy script) whenever code changes are deployed.
# Format: YYYY-MM-DD.N  (N = deploy count for that day, starting at 1)
BUILD_VERSION = "2026-08-04.3"

BUILD_FEATURES = [
    "public-langfuse-observability", # cached redacted production trace explorer for judges
    "queued-parallel-creative-generation", # two active image jobs plus three visible queued requests
    "smooth-creative-crop-export", # frame-paced dragging and async PNG encoding
    "autopilot-worker-transient-outage-recovery", # executor survives temporary Mongo failures
    "zalo-full-auto-creative-media-recovery", # send every generated creative once across auto analysis/restarts
    "autopilot-full-auto-creative-analysis", # full-auto starts VLM and resumes without operator refresh
    "autopilot-explicit-launch-boundary",    # every policy requires human approval before order creation
    "np6-placement-catalog",
    "np6-audience-topic-taxonomy-v2",
    "np6-context-first-zone-ranking",
    "np6-hybrid-placement-retrieval",
    "np6-nano-topic-reranking",
    "np6-hybrid-audience-retrieval",
    "np6-nano-audience-reranking",
    "np6-audience-pipeline-evidence",
    "np6-news-screenshot-zone-contract",
    "publisher-category-hero-policy",
    "general-homepage-placement-context",
    "zalo-semantic-audience-selection",
    "zalo-fully-automatic-milestones",
    "openai-format-aware-creative-assignment",
    "openai-generated-format-filenames",
    "openai-image-daily-quota-100",
    "mode-aware-brief-onboarding",
    "autopilot-complete-demo-briefs",
    "openai-mini-audience-query-planner",
    "openai-audience-sufficiency-fallback",
    "openai-audience-rerun-cache-bypass",
    "openai-audience-reasons-vietnamese",
    "openai-related-placement-options",
    "openai-placement-catalog-controls",
    "openai-guided-safe-auto-assignment",
    "openai-resilient-creative-upload",
    "walkthrough-creative-upload-retry",
    "openai-creative-platform-role-matching",
    "canonical-creative-identity-priority",
    "closest-ratio-assignment-fallback",
    "walkthrough-random-compatible-placements",
    "autopilot-placement-size-visibility",
    "guided-draft-list-mutations",
    "guided-audience-confirmation-gate",
    "guided-targeting-schema-repair",
    "openai-brief-working-draft-recovery",
    "brief-date-format-normalization",
    "walkthrough-brief-proposal-gate",
    "autopilot-chat-audience-reselection",
    "autopilot-creative-draft-poll-guard",
    "autopilot-safe-review-anchor",
    "autopilot-brief-gated-creative-source",
    "autopilot-explicit-creative-analysis",
    "autopilot-persistent-creative-results",
    "autopilot-chat-milestones",
    "zalo-exact-placement-page-capture",
    "creative-contain-blurred-fit",
    "hackathon-unicode-pdf-font",
    "mobile-manual-bottom-clearance",
    "adspilot-destructive-admin-surface-removed",
    "system-logs",
    "step-tool-rules",
    "brief-rules",
    "auto-confirm-apply",
    "auto-step-advance",
    "next-step-redirect",
    "3-level-tool-fallback",
    "confirmation-detection",
    "force-text-no-tools",
    "empty-response-guard",
    "frontend-console-log",
    "full-brief-update",
    "skip-update-workspace-llm",
    "dmp-recommend-fix",
    "audience-entry-recommend",
    "retry-last-chat",
    "persist-workspace-on-confirm",   # brief persisted to MongoDB on auto-apply/pending confirm
    "audience-entry-single-fire",     # removed double-fire of audience-entry trigger
    "report-step",                    # Step 5: AI-generated analytics + tabbed report UI
    "report-context-isolation",       # separate chat context for report step
    "report-polling",                 # frontend polls /api/reports/status every 3s
    "report-order-fetch",             # report-entry fetches real order from backend API for zones
    "report-zero-data-guard",         # regenerates if existing records are all zeros
    "report-debug-endpoint",          # GET /api/reports/debug/:campaignId for diagnostics
    "image-gen",                      # shared direct OpenAI GPT Image 2 service
    "image-gen-safe-zone",            # per-format safe-zone prompt constraints for correct crop
    "image-gen-canvas-crop",          # frontend canvas crop+resize to exact pixel dimensions
    "image-gen-quota",                # durable 20-output daily actor quota
    "creative-assets-conversation-scope", # reference assets cannot leak across chats
    "creative-walkthrough-assets-prompt", # walkthrough teaches assets and prompt composition without quota UI
    "creative-walkthrough-review-gate",  # walkthrough waits for analysis/manual review before Setup
    "creative-walkthrough-manual-review-auto-advance", # typing hands off to approval action
    "openai-autopilot-interactive-walkthrough", # real run edits audience, targeting, placements and assignments
    "autopilot-dual-creative-walkthrough", # randomly exercises uploaded or automatically prepared creatives
    "provider-neutral-campaign-ux",        # provider details stay at homepage selection only
    "autopilot-creative-placement-recovery", # crop/scale or generate missing formats without restarting run
    "autopilot-review-dock-layout",    # readable stacked review message and actions at narrow workspace widths
    "image-gen-lightbox",             # click-to-zoom lightbox in AI image gallery
    "image-gen-brief-preview",        # collapsible brief+audience preview in generator UI
    "email-step",                     # Step 6: PDF generation + Resend email delivery
    "email-pdf-pdfkit",               # PDF generated server-side via pdfkit (no puppeteer)
    "email-raw-export",               # CSV + JSON download endpoints for analytics records
    "email-resend",                   # email sent via Resend API (onboarding@resend.dev)
    "confirm-trigger-expanded",       # added duyệt/ổn rồi/ok rồi/hợp lý to confirm triggers
    "step-advance-llm-rule",          # LLM explicitly told update_workspace is only way to advance
    "llm-debug-logging",              # AGENT_DEBUG=true dumps full LLM input/output to stdout
    "llm-max-tokens-4096",            # raised LLM_MAX_TOKENS from 2000 to 4096
    "finish-reason-length-retry",     # retries with short context when LLM hits token limit
    "zone-conflict-detection",        # get_zone_list/search_zones annotate is_booked + conflict info
    "zone-date-injection",            # brief dates auto-injected into zone tool args from workspace
    "proposal-block-segment-display", # fixed [object Object] in WorkspaceProposalBlock for segment
    "confirm-segment-count-fix",      # fixed '0 segments' in confirm message when value is JSON string
    "zone-snapshot-enrichment",       # workspace snapshot resolves zone IDs to full details from catalog
    "creative-full-listing",          # all creative files listed in snapshot (not just first 4)
    "assignment-context",             # assignments sent from FE + shown in workspace snapshot
    "thinking-phrases-rotation",      # TypingIndicator rotates Vietnamese thinking phrases every 3s
    "thinking-elapsed-timer",         # shows elapsed seconds after 15s in thinking indicator
    "error-bubble-retry",             # null API response shows red error bubble with retry button
    "timeout-180s-all-ai",            # all AI-related fetch timeouts raised to 180s
    "ad-screenshot",                  # GET /api/agent/screenshot: Playwright full-page capture of live test sites
    "phase0-api-key-auth",            # X-API-Key middleware (no-op until AGENT_API_KEY set)
    "phase0-order-guard",             # deterministic server-side order validation before POST /api/orders
    "phase0-idempotent-orders",       # idempotencyKey dedup: retries can never double-book
    "phase0-rate-limiting",           # SlowAPI: 30/min chat, 10/min recommends
    "phase0-prometheus-metrics",      # /metrics + agent_* counters
    "phase0-langfuse-tracing",        # drop-in via langfuse.openai when keys set
    "phase1-langgraph-chat",          # graph path behind USE_LANGGRAPH_FREEFORM flag
    "phase1-auto-mode",               # planner→executor→critic subgraph, human-gated
    "phase1-stale-channel-fix",       # per-turn reset of transient graph channels + per-graph threads
    "session-default-merge",          # get_or_create_session always returns full doc shape
    "phase2-rag-audience",            # versioned hybrid retrieve→LLM behind USE_RAG_AUDIENCE
    "phase2-rag-query-rewrite",       # raw+coverage-preserving rewrites behind separate flag
    "phase2-rag-index-integrity",     # catalog fingerprint + model/runtime metadata readiness
    "phase2-rerank-integrated",       # Qwen MaaS adapter retained; disabled after eval regression
    "phase2-rag-eval-gates",          # stable segmentId metrics + retrieval/end-to-end reports
    "rag-negative-intent-guard",      # deterministic pre-selector filtering for explicit exclusions
    "eval-production-rate-pacing",    # canonical eval respects the deployed recommendation limit
    "langfuse-windows-console-fix",   # tracing init no longer fails on cp1252 console output
    "phase3-creative-intel",          # PIL deterministic pass + review queue + optional VLM
    "phase3-durable-creative-worker", # Mongo-backed recoverable creative analysis jobs
    "phase3-preorder-vlm-gate",       # verdict + audited override required before order
    "phase3-intended-format",         # explicit placement format beats weak VLM layout inference
    "setup-entry-history-fix",        # proactive setup message is persisted before next chat turn
    "dependency-aware-readiness",     # /ready verifies MongoDB + backend before receiving traffic
    "reproducible-local-stack",       # frontend + seeded backend + agent + observability via Compose
    "transactional-campaign-workspace", # revisioned canonical artifacts + typed proposals
    "nonlinear-artifact-recompute",     # dependency-aware stale/reuse orchestration
    "durable-campaign-autopilot",       # persisted runs/tasks, leases, review, pause/resume/cancel
    "autopilot-creative-source",         # explicit upload or autonomous AI-generation run policy
    "autopilot-idempotent-image-gen",    # exact-size asset provenance + storage recovery checkpoint
    "np2-canonical-audience-reach",       # one server reach contract across Agent flows and UI
    "np3-openai-creative-studio",         # named assets, prompt composer, GPT Image 2 and nano VLM
    "np4-semantic-faq-coordinator",       # structured FAQ/action planning plus grounded read tools
    "np5-report-evidence-contract",       # traceable metrics and semantic evidence-cited report Q&A
    "autopilot-lease-heartbeat",         # long provider calls retain durable worker ownership
    "advertising-agent-blue-ui",        # Zalo-inspired original blue identity + two-mode selector
    "switchable-mode-canvases",          # Guided/Autopilot tabs with durable desktop/mobile state
    "campaign-strategy-simulator",      # three deterministic, auditable strategy scenarios
    "autopilot-live-evidence",          # trace, retrieval, rerank, guard and idempotency evidence
    "autopilot-approved-brief-gate",    # never persist or run against an unapproved chat brief
    "autopilot-stable-run-trace",       # stable run-level trace instead of polling request IDs
    "autopilot-worker-start-guard",     # reject runs when no worker can execute the durable plan
    "autopilot-guided-entry-isolation", # Guided proactive messages never leak into Autopilot
    "typed-brief-collector",             # complete recommendations always become durable proposals
    "authoritative-campaign-clock",      # yearless dates grounded to Asia/Ho_Chi_Minh server time
    "openai-in-progress-date-window",    # yearless OpenAI ranges stay current while their end date has not passed
    "openai-brief-transport-normalization", # clarification working drafts cannot fail or mutate the strict Brief domain
    "nonblocking-llm-io",                # slow providers no longer freeze workspace polling
    "brief-budget-unit-normalization",   # raw VND from providers is normalized to workspace millions
    "external-qa-contract-hardening",    # independent cases continue and validation labels inventory honestly
    "parallel-rag-query-io",             # rewritten Qdrant reads run concurrently off the event loop
    "rag-runtime-readiness",             # ready waits for cached FastEmbed runtime prewarm
    "privacy-security-hardening",       # redaction, deletion, prompt guard and bounded requests
    "provider-circuit-breaker",         # timeout, bounded retry, fail-fast and policy-gated fallback
    "namespaced-demo-rehearsal",        # safe fallback + reset/prewarm/rehearsal tooling
    "fe2b-local-accounts",              # Argon2id local registration/login behind one user model
    "fe2b-revocable-account-sessions",  # opaque hashed HttpOnly sessions + remote revocation
    "fe2b-csrf",                        # centralized double-submit protection for cookie mutations
    "fe2b-explicit-conversation-claim", # atomic device-to-account transfer without artifact copies
    "fe2b-cross-device-resume",         # account history restores canonical conversation state
    "zalo-login-pkce",                  # Social OAuth v4 mapped to the FE-2B account session
    "zalo-explicit-identity-link",       # existing local users prove both sessions before linking
    "zalo-oa-signed-webhook",            # fail-closed raw-body signature verification + dedupe
    "zalo-webhook-provider-ack",          # provider-required 200 without accepting invalid events
    "zalo-oa-one-time-channel-link",     # signed OA message joins separate channel/account identities
    "zalo-oa-signed-follow-link",        # follow widget UX; signed follow event consumes explicit attempt
    "zalo-oa-v3-existing-follower-link", # recover already-following users through OA V3 identity mapping
    "zalo-oa-rotating-token-store",      # persist every single-use refresh-token rotation atomically
    "zalo-brand-mark",                   # consistent official-style Zalo mark and exact brand blue
    "zalo-oa-widget-first-auto-check",   # lead with a large OA widget and silently recover followers
    "zalo-follow-webhook-schema",        # normalize follower.id and top-level oa_id from real follow events
    "zalo-existing-follower-retry",      # retry OA burst limits without caching false follower misses
    "csrf-self-healing-retry",           # rotate stale double-submit cookies and safely retry once
    "legacy-brief-approval-recovery",    # reconstruct and atomically approve model-only Briefs
    "zalo-durable-agent-worker",         # leased inbound turns, outbox sends and restart recovery
    "zalo-owned-campaign-resolver",      # server-owned exact/active/ambiguous campaign selection
    "zalo-report-qa",                    # reuse the existing six-view report module
    "zalo-confirmed-campaign-lifecycle", # pause/resume only after expiring explicit confirmation
    "zalo-two-mode-autopilot-progress",  # fully automatic or important-gate progress over OA
    "zalo-openai-tool-controller",       # GPT-5.4-mini selects strict server-owned tools over Responses API
    "zalo-time-bounded-chat-sessions",   # one-hour hard / twenty-minute idle context boundaries
    "zalo-rolling-conversation-memory",  # asynchronous structured summaries bridge later OA sessions
    "zalo-30-message-token-context",     # recent-session context with a server-side total token budget
    "zalo-native-report-images",         # six existing reports rendered as OA-safe images
    "zalo-detailed-report-pages",        # three OA-safe pages cover KPIs, trends and zone performance
    "zalo-report-explicit-campaign",     # new report requests never silently select active/only campaign
    "zalo-opaque-pdf-export",            # expiring hashed media link serves the existing full PDF
    "zalo-guided-help-copy",             # warm intro plus campaign-neutral example guidance
    "zalo-ordered-live-captures",        # per-site heading, zone crops, then annotated full page
    "zalo-one-mb-image-guard",           # provider-safe compression + expiring full-resolution fallback
    "post-launch-report-generation",     # order commit starts the existing idempotent report pipeline
    "complete-unicode-report-pdf",       # embedded Unicode fonts + six full chart/Q&A report sections
    "shared-report-pdf-download",        # Guided and Autopilot outcomes expose the same full PDF action
    "report-pdf-readiness-gate",         # Zalo only delivers PDF after all six report types are ready
    "zalo-owned-workspace-link",          # model tool returns only an ownership-checked conversation deep link
    "zalo-autopilot-web-continuity",      # Zalo runs appear and live-refresh in account campaign history
    "guided-shared-audience-retrieval",   # Copilot and Autopilot share catalog-grounded audience selection
    "guided-audience-stable-dedupe",      # repeated provider labels cannot duplicate a catalog segment
    "guided-actionable-brief-clarification", # missing Brief fields always render as explicit questions
    "guided-model-led-brief-delegation",   # ask by default; infer advisory fields only when naturally delegated
    "guided-conversation-audience-reset", # a new/resumed campaign cannot retain old recommendation cards
    "guided-conversation-request-isolation", # late proactive responses are discarded after campaign switches
    "guided-explicit-creative-review",       # terminal analysis remains visible until operator confirmation
    "durable-account-campaign-ownership",    # campaign discovery survives transcript deletion
    "guided-order-response-normalization", # setup preserves guard details and successful order metadata
    "guided-live-conflict-recovery",       # commit-time booking conflicts refresh zones for safe reselection
    "audience-unknown-size-semantics",     # missing catalog size is never presented or prompted as zero people
    "audience-modeled-size-backfill",      # missing catalog ranges receive labeled, stable Vietnam estimates
    "guided-creative-intel-review",        # completed Copilot creatives retain VLM evidence and manual review
    "guided-assignment-alert-recovery",    # stale/missing zone assignments expose safe repair choices
    "guided-creative-terminal-gate",       # queued analysis cannot present Creative as complete or enter Setup
    "guided-server-derived-resume-step",   # history restores durable order/report progress across devices
    "public-experience-revamp",           # landing, progressive onboarding, safe dual-mode demos and current docs
    "guided-interface-tours",             # real Copilot/Autopilot UI spotlight tours with launch safety boundary
    "kinetic-public-landing",              # code-native agentic campaign constellation and clear workspace entry
    "connected-campaign-landing",          # linked brief-to-decision story with distinct mode visual systems
    "autopilot-in-layout-guide",           # persistent brief, creative, control and run-reading guidance
    "copilot-walkthrough-mode-retention",  # live walkthrough prepares a campaign without returning home
    "seamless-campaign-signal-loop",        # three-copy rail loops without a Zalo-to-Brief animation snap
    "bidirectional-landing-reveals",        # campaign truth and mode sections fade on scroll entry and exit
    "rolling-demo-date-window",             # walkthrough dates stay yesterday through seven days later
    "contained-signal-ribbon",              # shallow rail tilt and lower track prevent boundary clipping
    "viewport-anchored-workspace",          # campaign entry cannot inherit homepage window scroll offset
    "workspace-shell-scroll-reset",         # layout-phase reset clears retained shell scroll before paint
    "non-scrollable-workspace-shell",        # outer app clips overflow; only child panes may own scroll state
    "advertising-agent-mascot",              # generated robot identity anchors the public hero and brand lockup
    "glass-brand-command-bar",               # compact live-signal navigation replaces the sparse top divider
    "conversation-model-lock",                # one immutable campaign provider is selected per run
    "openai-campaign-engine-foundation",       # isolated OpenAI engine boundary, catalogued but not enabled
    "openai-semantic-turn-router",             # typed FAQ/action/mixed/clarification planning
    "openai-responses-tool-loop",              # bounded strict Responses API function execution
    "openai-durable-workspace-proposals",       # validated mutations remain pending until semantic approval
    "openai-guided-provider-routing",           # model-backed Guided entries honor the immutable run model
    "openai-guided-model-purity",               # OpenAI Brief/Audience/RAG never call GreenNode inference
    "openai-autopilot-model-propagation",        # workers, retries and resume use the persisted run model
    "openai-autopilot-model-purity",             # OpenAI audience/Q&A never call GreenNode inference
    "zalo-autopilot-model-policy",               # Zalo-created runs use an explicit channel model policy
    "openai-campaign-engine-ready",               # OpenAI becomes selectable only when configured server-side
    "openai-typed-brief-intake",                  # initial Copilot briefs collect all supplied fields through OpenAI
    "conversation-model-workspace-provenance",   # workspace footer names the immutable provider selected for the run
    "openai-langfuse-turn-tracing",              # complete OpenAI prompts, responses, tools and errors share one turn trace
    "autopilot-reviewed-creative-repair",        # approved uploads supersede a failed AI-generation proposal
    "autopilot-replan-result-generation",       # rerun task commits replace their own stale artifacts safely
    "openai-multi-topic-audience-search",        # semantic topic queries merge catalog matches without selecting them
    "openai-deferred-proposal-disposition",      # not-yet approval keeps a proposal pending for later confirmation
    "provider-aware-creative-vlm",                # uploaded creative analysis follows the immutable campaign model lock
    "creative-vlm-failure-retry",                 # provider failures requeue while genuine review verdicts stay terminal
    "openai-vlm-brief-fit-consistency",           # derive fit score from anchored visual evidence and gate critical mismatches
    "autopilot-critical-review-checkpoints",       # shared legacy policy stops at five operator checkpoints
    "openai-autopilot-streamlined-semi-automatic", # OpenAI audience and targeting auto-commit when quality gates pass
    "openai-autopilot-related-audience-fallback",  # delegated modes select top-ranked related rows when direct is empty
    "openai-autopilot-contextual-targeting",        # brief/audience-aware basic and advanced catalog targeting
    "autopilot-review-question-safety",             # review questions never become approvals and receive artifact-grounded answers
    "report-once-only-showcase-disclosure",         # report model reasons on metrics without repeating UI-only showcase provenance
    "autopilot-report-resume-routing",               # completed runs use report Q&A even when resume restores stale step metadata
    "openai-report-suggestion-safety",                # report follow-ups stay within supported read-only analysis
    "autopilot-placement-intent-checkpoint",          # critical review stops at the editable preliminary placement proposal
    "zalo-campaign-comparison-summary",               # one owned campaign-list call exposes budget and dates for comparisons
    "zalo-tool-error-observability",                  # Zalo model/tool failures are recorded without weakening mutation safety
    "mobile-adaptive-guidance-ui",                    # target-aware tours, compact review controls and touch-safe creative crop
    "quality-data-foundation",                        # versioned interactions, quality events and feedback
    "run-feedback",                                   # owned idempotent Guided/Autopilot feedback
    "typed-guardrail-policy",                         # legacy-compatible enforce + shadow decision modes
    "owned-agent-order-reads",                        # campaign status tools use server-derived ownership scope
    "privacy-safe-zone-conflicts",                    # availability omits other campaign identity
    "autopilot-preference-sequence",                  # creative approach unlocks approval-policy choice with chat guidance
    "autopilot-skip-analysis-order-guard",             # explicit server-side skip verdicts remain valid at both safety gates
    "autopilot-active-checkpoint-routing",             # completed audience tasks cannot steal later checkpoint commands
    "autopilot-checkpoint-chat-grounding",             # review Q&A prioritizes bounded evidence for the active checkpoint
    "autopilot-faq-valid-bounded-input",                # oversized review artifacts retain exact questions in valid JSON
    "report-budget-delivery-normalization",             # new synthetic delivery stays within budget without ratio drift
    "zalo-creative-review-ui-parity",                    # analyze/skip semantics, one-time OA-safe creative delivery
    "creative-analysis-auto-resume",                      # completed VLM jobs wake Zalo and Agent UI without a manual refresh
    "autopilot-walkthrough-analysis-choice",              # walkthrough follows the explicit analyze choice and automatic verdict refresh
    "walkthrough-paced-creative-review",                   # creative analysis and assignment pause at explicit read checkpoints
    "responsive-header-attention-controls",                # confirmed reset plus safe animated Tour and mobile bottom helper
    "viewport-rooted-header-dialogs",                       # header dialogs portal to the viewport instead of the backdrop-filter containing block
    "demo-v2-placement-creative-first",                     # new Autopilot runs place creative planning before audience and targeting
    "durable-generated-image-gallery",                      # raw and cropped AI creatives survive refresh and navigation
    "parallel-creative-generation-gallery",                 # image jobs run in parallel while explicit gallery selection remains user controlled
    "full-bleed-znews-skin-generation",                      # side-skin creatives contain no synthetic grey docking strip
    "centered-znews-category-masthead",                      # category mastheads remain centered across shared and dynamic layouts
    "deterministic-creative-manual-override",                # documented numbered approval works identically in Agent UI and Zalo
    "production-grafana-openai-observability",               # current OpenAI/Zalo/tool paths populate zero-safe Agent Ops panels
    "production-creative-image-url-recovery",                # generated gallery and crop retain the CORS-enabled backend asset URL
    "generated-image-finalize-upload-limit",                 # owned crop and scale payloads can carry full-resolution canvas output
]
