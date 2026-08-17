# Zalo OA Conversational Tool Agent — Technical Approach

Status: implementation plan for the post-FE-3 Zalo OA conversational upgrade.

## 1. Outcome

The Zalo OA assistant becomes a channel-native conversational agent instead of a fixed intent router. GPT-5.4 mini receives bounded conversational context and a strict set of server tools. It decides whether it can answer conversationally, needs to ask a clarification question, or needs one or more tools. The server remains the authority for identity, campaign ownership, confirmation, data retrieval, and side effects.

This slice does not change the web Guided/Autopilot experiences, introduce a second campaign database, or add an analytics agent. Reports continue to use the six existing synthetic report views. Existing campaigns remain read-only except for explicit pause/resume. New campaigns continue through the existing Campaign Autopilot service.

## 2. Architectural boundary

The model may:

- understand Vietnamese, shorthand, pronouns, typos, and follow-up references;
- decide which tool or sequence of tools is necessary;
- provide tool arguments such as a campaign reference, report view, or question;
- synthesize a concise answer from canonical tool results;
- ask for missing or ambiguous information.

The model may not:

- provide an owner, user ID, account ID, session ID, or arbitrary backend URL;
- enumerate campaigns outside the server-resolved actor;
- bypass campaign ambiguity checks;
- directly pause, resume, launch, or approve anything;
- treat a prior summary as authoritative campaign state.

All tools receive a server-side execution context containing the channel thread and already-resolved actor. Tool schemas deliberately contain no ownership identifiers.

## 3. Time-based chat sessions

The permanent `channel_threads` record remains the durable relationship between an OA sender and the existing Advertising Agent identity/conversation. A new additive `channel_chat_sessions` collection organizes that permanent Zalo stream into context sessions.

A chat session closes when either condition is reached:

- hard lifetime: 60 minutes from `started_at`;
- idle lifetime: 20 minutes since `last_activity_at`.

The hard lifetime guarantees a bounded unit even during continuous chat. The idle boundary prevents unrelated conversations later in the hour from inheriting stale working context. Campaign selection and Autopilot subscriptions remain thread state. Unexecuted confirmation state is cleared at a session boundary and must be requested again.

Each chat-session document contains:

```text
chat_session_id, thread_id, sequence, status
started_at, last_activity_at, expires_at, closed_at, close_reason
messages[{seq, role, content, created_at, token_estimate}]
message_count, token_estimate
summary{summary, user_goals, campaigns_discussed, resolved_questions,
        unresolved_questions, decisions, user_preferences, last_topic,
        last_campaign_reference}
summary_up_to_seq, summary_status, summary_attempts,
summary_lease_owner, summary_lease_expires_at, summary_error
```

Indexes are additive and safe on existing Mongo data:

- unique `(thread_id, sequence)`;
- unique partial `(thread_id, status)` where `status = open`;
- `(thread_id, started_at desc)` for memory lookup;
- `(summary_status, summary_lease_expires_at, last_activity_at)` for the worker.

No existing document is rewritten. The first new message creates sequence 1 lazily.

## 4. Context assembly

Every inbound and outbound text is dual-written:

1. the existing `agent_sessions` history, preserving the web-visible canonical transcript;
2. the active `channel_chat_sessions` message list, used for Zalo model context.

The model context contains, in order:

1. stable system instructions and tool definitions;
2. the latest completed bridge summary from the previous session, when available;
3. the current session's newest messages, capped at 30 messages;
4. the newest user message, which is never dropped.

The total estimated input budget defaults to 24,000 tokens. A single message is capped at approximately 6,000 tokens, tool results at 8,000 tokens, and the bridge summary at 1,200 tokens. The assembler drops oldest messages first. Token estimation is local so context assembly does not add an API round trip.

## 5. Background rolling summaries

Summarization is asynchronous and never blocks the first message of a new session. A session is queued when it closes, or while open after at least eight new messages / about 4,000 unsummarized tokens. The existing Zalo worker claims summary jobs using a lease, calls GPT with structured output, and updates `summary_up_to_seq` atomically.

The summary records goals, discussed campaigns, decisions, unresolved questions, preferences, last topic, and last campaign reference. It explicitly excludes secrets and does not invent current campaign facts. If a final summary is not ready at rollover, the context bridge uses the last completed rolling summary plus a small bounded unsummarized tail. Tool calls still re-fetch all operational facts.

## 6. Tool surface

Read tools:

- `list_campaigns(status)`
- `get_campaign_status(campaign_reference)`
- `get_campaign_setup(campaign_reference)`
- `get_campaign_report(campaign_reference, view, question)`
- `get_campaign_live_view(campaign_reference)`
- `get_autopilot_progress(campaign_reference)`
- `search_conversation_memory(query)`

Workflow tools:

- `prepare_pause_campaign(campaign_reference)`
- `prepare_resume_campaign(campaign_reference)`
- `begin_autopilot(mode)`
- `submit_autopilot_brief(brief)`

The lifecycle tools only create an expiring confirmation proposal. The existing exact confirmation/rejection gate performs the mutation after re-fetching owned campaigns. Autopilot brief confirmation and launch review retain the same server-side guard. Unsupported edits to existing campaign configuration return a structured capability error.

Campaign resolution occurs only among `owned_campaigns(thread)`. A unique match becomes the thread's active campaign. An ambiguous result is returned to the model with safe candidate labels and IDs so it can ask one targeted question. No browser- or model-provided ownership field is accepted.

## 7. Responses API controller

Each turn uses the Responses API with `store=false`, `tool_choice=auto`, strict JSON schemas, and parallel tool calls disabled. The controller repeats:

1. send instructions, bounded context, and tools;
2. inspect `function_call` outputs;
3. validate and execute each call on the server;
4. append matching `function_call_output` items;
5. request the next model step.

The loop is bounded to five rounds and eight calls. Invalid arguments become structured tool errors that the model can recover from. Read-tool failure may be explained to the user; model/provider failure fails closed and performs no mutation. Live-view image parts are retained server-side while the model writes the accompanying text.

## 8. Safety and reliability

- OpenAI receives a one-way hashed safety identifier, never the raw OA sender or internal user ID.
- API keys, OA tokens, passwords, and account session tokens are never placed in prompts, responses, logs, or traces.
- `store=false` is used because Advertising Agent owns conversation retention.
- Tool results are size-capped before returning to the model.
- Every mutation proposal expires after five minutes and is invalidated on session rollover.
- Ownership is checked both when preparing and executing a lifecycle action.
- A provider outage never falls back to blind keyword-driven campaign mutations.
- Durable event and outbound idempotency remain unchanged.

## 9. Verification plan

Focused tests cover:

- hard and idle rollover, atomic single-open-session behavior, and pending-action clearing;
- 30-message ordering and token-budget truncation;
- summary queue leasing, retry, structured persistence, and non-blocking rollover;
- multiple tool rounds and strict function outputs;
- greetings producing no campaign disclosure or tool call;
- ambiguous references producing safe choices;
- ownership isolation and no owner arguments in schemas;
- pause/resume requiring explicit confirmation and rechecking ownership;
- report/setup/live tools using existing services;
- Autopilot initiation using the existing workflow;
- OpenAI failure producing no side effect.

Then run the complete Agent suite, the frontend production build, deploy behind the current rollback procedure, and perform two-account/OA acceptance checks without reseeding Mongo.

## 10. Rollout and rollback

The migration is lazy and additive. New indexes are created at startup. Existing channel threads, identities, events, subscriptions, account ownership, conversations, sessions, workspaces, orders, and reports are untouched.

Deployment takes a timestamped server backup before copying files and restarting the existing Python authority. Rollback restores that directory snapshot and restarts the same PM2 process. There is no destructive data migration to reverse; `channel_chat_sessions` can remain unused by the older build.

## 11. OpenAI implementation references

- [GPT-5.4 mini model](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)

The controller deliberately uses local/manual conversation state with `store=false`. This avoids coupling Advertising Agent retention to provider-side response storage while still following the documented function-call, server execution, and `function_call_output` loop.
