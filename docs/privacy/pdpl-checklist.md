# Vietnam personal-data protection checklist

Status as of 2026-07-15. This checklist is implementation evidence, not a declaration of full legal compliance.

Authoritative references: [Law 91/2025/QH15](https://vbpl.vn/bokhoahoccongnghe/Pages/vbpq-thuoctinh.aspx?ItemID=179252&Keyword=) is listed as in force from 1 January 2026; [Decree 356/2025/NĐ-CP](https://vanban.chinhphu.vn/?classid=1&docid=216387&orggroupid=2&pageid=27160) is the implementing decree, also effective 1 January 2026.

| Control | Status | Evidence / gap |
|---|---|---|
| Data inventory and purpose mapping | Implemented | `docs/privacy/data-inventory.md` |
| User notice at collection | Implemented for demo | Opening selector and first boot response disclose AI processing and minimization |
| Data minimization | Partly implemented | Request limits, compact creative metadata, no user data in Qdrant; live inference still contains necessary campaign text |
| Logs/traces protected | Implemented | Recursive Python/Node redaction; Langfuse mask hook; live tests prove email/phone/password absent from backend logs |
| Retention | Partly implemented | 30-day agent-session and backend API-log TTL; workspace/checkpoint and creative-file retention require expansion |
| User/session deletion | Implemented for local session owner | New Chat invokes session deletion; agent/workspace/run/checkpoint records removed; orders retained |
| Security safeguards | Implemented release-candidate subset | BFF credential boundary, local-only published ports, size limits, rate limits, prompt guard, order guard, idempotency, circuit breaker |
| Third-party/transfer governance | Documented gap | Generation fallback defaults off for confidential data; contracts, region, transfer assessment and Langfuse retention need operator/legal sign-off |
| Sensitive-data handling | Partly implemented | Common PII/credential shapes redacted; application does not need or intentionally collect sensitive identity data |
| Data-subject request process | Documented gap | Session deletion exists technically; authenticated request/identity verification and operator procedure are not complete |
| Incident response | Partly implemented | Correlated request IDs, SLO alerts and simulated-provider postmortem; formal notification process needs legal/operations ownership |
| Impact assessment / required dossiers | Not complete | Must be assessed and prepared by qualified Vietnamese counsel before public processing |

Release decision: suitable for a controlled local hackathon demo with synthetic campaign data. Do not present this checklist as production legal approval.
