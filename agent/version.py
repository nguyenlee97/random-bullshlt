"""Build version — separate module so handlers can import it without
touching main.py (kills the main→router→boot→main circular import)."""
# ── Build version ─────────────────────────────────────────────────────────────
# Bump this manually (or via deploy script) whenever code changes are deployed.
# Format: YYYY-MM-DD.N  (N = deploy count for that day, starting at 1)
BUILD_VERSION = "2026-07-17.1"

BUILD_FEATURES = [
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
    "image-gen",                      # POST /api/agent/generate-image via gpt-image-1
    "image-gen-safe-zone",            # per-format safe-zone prompt constraints for correct crop
    "image-gen-canvas-crop",          # frontend canvas crop+resize to exact pixel dimensions
    "image-gen-quota",                # 10-image per-session limit tracked server-side
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
    "autopilot-lease-heartbeat",         # long provider calls retain durable worker ownership
    "advertising-agent-blue-ui",        # Zalo-inspired original blue identity + two-mode selector
    "switchable-mode-canvases",          # Guided/Autopilot tabs with durable desktop/mobile state
    "campaign-strategy-simulator",      # three deterministic, auditable strategy scenarios
    "autopilot-live-evidence",          # trace, retrieval, rerank, guard and idempotency evidence
    "autopilot-approved-brief-gate",    # never persist or run against an unapproved chat brief
    "autopilot-stable-run-trace",       # stable run-level trace instead of polling request IDs
    "typed-brief-collector",             # complete recommendations always become durable proposals
    "authoritative-campaign-clock",      # yearless dates grounded to Asia/Ho_Chi_Minh server time
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
]
