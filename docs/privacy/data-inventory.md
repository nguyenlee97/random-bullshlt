# Advertising Agent — data inventory

Last reviewed: 2026-07-15. This is an engineering inventory, not a legal opinion.

The current legal reference is Vietnam’s Law on Personal Data Protection No. 91/2025/QH15, effective 1 January 2026, as listed by the [National Database of Legal Documents](https://vbpl.vn/bokhoahoccongnghe/Pages/vbpq-thuoctinh.aspx?ItemID=179252&Keyword=). Decree 356/2025/NĐ-CP took effect on the same date and implements that law, according to the [Government legal-document portal](https://vanban.chinhphu.vn/?classid=1&docid=216387&orggroupid=2&pageid=27160).

## Stored data

| Data | Purpose | Store | Default retention | Deletion behavior |
|---|---|---|---|---|
| Chat messages and session state | Continue Guided/Copilot work | MongoDB `agent_sessions` | 30-day TTL | `DELETE /api/agent/sessions/{session_id}` |
| Campaign workspace, proposals, revisions and append-only events | Safe non-linear edits and audit | MongoDB workspace collections | Session lifecycle; TTL expansion still required | Session deletion removes records by both session ID and workspace ID; a dry-run orphan cleanup exists for legacy rows |
| Autopilot runs, tasks and events | Durable planning, pause/review/recovery | MongoDB agent-run collections | Session lifecycle; TTL expansion still required | Session deletion removes run/task/event records |
| LangGraph checkpoints | Conversation/orchestration recovery | MongoDB checkpoint collections | Session lifecycle | Session deletion removes session and auto thread IDs |
| Agent logs | Diagnostics | MongoDB `agent_logs`, stdout | Session lifecycle | Redacted before storage; session deletion removes Mongo records |
| Backend API logs | Operations | MongoDB `api_logs` | 30-day TTL | Automatic TTL; manual admin clear exists |
| Uploaded creative files | Campaign setup and analysis | Backend upload directory | No automatic TTL yet | Individual delete endpoint; automatic campaign-archive deletion is a documented gap |
| Creative analysis and OCR | Suitability/safety review | MongoDB creative job/workspace data | Session lifecycle | Session deletion removes agent job/workspace records |
| Orders and campaign records | Business/audit record | Backend MongoDB collections | Business retention policy | Intentionally not deleted with chat/session data |
| Audience vectors | Retrieval over catalog segments | Local Qdrant | Until index rebuild | Catalog data only; no user chat should be indexed |
| Metrics | Aggregate reliability and latency | Local Prometheus | Local volume policy | No raw prompt/body labels |
| Traces | Model quality and diagnostics | Configured Langfuse service | Provider/project setting | Inputs/outputs are redacted first; retention and region need operator confirmation |

## External processing flows

| Destination | Sent | Control |
|---|---|---|
| Primary GreenNode MaaS model | Chat context, brief/workspace context needed for generation | 45-second deadline, bounded retry, PII removed from traces but not from live inference payload |
| GreenNode reranker | Query and candidate segment text | Catalog/query only; retrieval fallback available |
| GreenNode VLM | Creative image and bounded brief context | Explicit feature flag; failure requires human review |
| OpenAI fallback/critic | Critic/evaluation content; generation fallback only when enabled | Cross-provider generation fallback defaults off and also requires an allowed data classification |
| Langfuse | Redacted trace input/output and operational metadata | Mask hook plus explicit redaction; no API keys or raw creative bytes |

## Data-minimization boundaries

- The browser sends creative URLs and compact metadata to the agent; it does not send persisted `dataUrl` content through normal agent requests.
- Agent and backend request logs redact email, Vietnamese phone numbers, 12-digit citizen IDs, bearer tokens, known API-key shapes, database credentials, and sensitive fields.
- Raw model inference still needs the campaign text supplied by the user. The UI and boot message therefore tell users not to enter unnecessary personal or secret data.
- Orders are outside session deletion because they are business records. The UI must not imply that New Chat deletes created orders.

## Open privacy work before a public release

- Legal review of role, lawful basis/consent language, notices, data-subject request procedure, and any required impact/transfer dossiers.
- Confirm processor contracts, location and retention for every MaaS, OpenAI and Langfuse project.
- Add automatic creative-file retention/deletion tied to campaign archival.
- Add TTL/index policy to all workspace, run, event and checkpoint collections, not only sessions and API logs.
- Authenticate data-subject/session deletion so one user cannot delete another user’s session.
