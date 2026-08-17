# Copy-ready prompt for the next Codex task

```text
Continue the Advertising Agent project in:
C:\Users\LENOVO\Downloads\Claw-a-thon-20260605T160536Z-3-001\random-bullshlt

Execute FE-2B: local accounts, secure account sessions, explicit anonymous-conversation claim, and cross-device conversation resume.

Before editing:
1. Read AGENTS.md and every relevant file in docs/knowledge base.
2. Read docs/next-hackathon/19-final-enhancement-phase-roadmap.md.
3. Read and follow docs/next-hackathon/20-fe2b-local-accounts-handoff.md completely.
4. Inspect the current implementation, especially agent/identity.py, agent/router.py, agent/main.py, agent/config.py, agent/tests/test_identity_conversations.py, agent_frontend/src/api/agentApi.js, App.jsx, ExperienceSelector.jsx and ConversationHistory.jsx.
5. Confirm the starting branch/commit. Expected branch: revamp/next-hackathon. Expected rollback commit: 3eea598.

Implement the full FE-2B slice, not only a UI mock:
- local email/password registration and login using Argon2id;
- opaque, hashed, revocable HttpOnly account sessions;
- logout and GET /auth/me;
- centralized CSRF protection for browser cookie-authenticated mutations;
- one server-side actor resolver for anonymous and account ownership;
- additive Mongo models/indexes with migration compatibility;
- explicit, atomic conversation claim that preserves conversation/session IDs and every campaign artifact;
- account-owned history and cross-device resume;
- homepage/history/workspace login, account and claim UX;
- focused security/ownership tests, all existing tests, production build and two-browser acceptance evidence;
- current-state/evidence documentation and a final commit.

Non-negotiable constraints:
- Anonymous usage must remain available without login.
- Login must never automatically claim conversations.
- Never trust browser-provided user/owner IDs.
- Never store account tokens or passwords in localStorage, responses, logs or traces.
- A claimed conversation must become inaccessible to the old anonymous identity after logout.
- Do not create a second auth authority in the Node backend.
- Do not implement Google, Zalo Login, Zalo OA, organization RBAC, Qwen reranking or the analytics agent in this task.
- Preserve legacy evaluator sessions and all current Guided/Autopilot behavior.
- Do not reseed/delete Mongo data.
- Preserve and do not commit the user-owned untracked AGENTS.md and agent/graph/README.md files.
- Respect every safety and rollback rule in the handoff document.

Use reasonable implementation judgment and proceed without asking me to choose routine technical details. Pause only if a decision would materially change product scope or require new external credentials/services. Keep me updated while you work. At completion, report files changed, schemas/APIs, test counts, browser journeys, migration behavior, known follow-ups and commit hash.
```

