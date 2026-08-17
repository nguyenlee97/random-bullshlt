# ADR 009 — Recoverable in-process creative worker

**Date:** 2026-07-15
**Status:** Accepted for the hackathon-scale deployment

## Context

Creative analysis used to be launched with `asyncio.create_task()` during final
order confirmation. The order did not wait for the verdict and a process
restart lost the task. Adding Redis and Celery would add another production
service before the workload requires one.

## Decision

Use MongoDB collection `creative_intel_jobs` as both the durable queue and the
verdict store. The FastAPI process starts one worker that atomically claims a
`queued` document, performs deterministic and VLM analysis, and persists a
terminal `auto_approved` or `needs_review` verdict. On startup, every job left
in `analyzing` is returned to `queued`, because the current deployment has one
worker process and the previous owner cannot still be alive.

Human overrides do not replace the original verdict. They append actor,
reason, timestamp, original status, and original reasons; consumers see the
derived status `approved_override`.

## Consequences

- Jobs and verdicts survive an agent restart.
- The UI can poll a stable analysis ID.
- Order validation can read the verdict independently of browser state.
- Horizontal agent replicas are not yet supported. Before adding replicas,
  introduce leases/heartbeats or move the queue to a dedicated worker system.
- A VLM failure is terminal `needs_review`, never silent approval.
