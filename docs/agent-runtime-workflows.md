# Agent Runtime Workflows (Durable + Slack-First)

## Actors

1. SlackBot: Slack edge adapter and UX streamer.
2. API: stateless write/read router and SSE projection endpoint.
3. Postgres: durable control plane and orchestration state machine.
4. Worker: claims execution rows, runs runtime I/O, writes durable events.
5. Runtime container: dumb Amp stdin/stdout process (`--stream-json` + `--stream-json-input`).

## Canonical Slack Turn Workflow

1. Slack event arrives (`team_id`, `channel`, `thread_ts`, `event_id`) and is deduped.
2. SlackBot calls `POST /agent/spawn` with `thread_key`, `spawn_id`, `persona_id`, optional `agents_md_override`.
3. Spawn resolves persona prompt, pins runtime assignment, returns `assignment_generation`.
4. SlackBot writes one or more `POST /agent/message` rows with Amp JSON `event` payloads.
5. API persists attachment bytes to `agent_attachments`, rewrites transcript payload to `attachment_ref` blocks.
6. SlackBot calls `POST /agent/execute` with `execute_id` and `assignment_generation`.
7. API durably inserts execution row and final-delivery obligation row in one transaction.
8. Worker claims execution, reconstructs stdin snapshot from transcript + attachments, writes Amp JSON lines to runtime stdin.
9. Worker persists raw stdout events (including thinking blocks) before emitting projections.
10. SlackBot streams projected chunks to Slack via `chat.startStream` + `chat.appendStream`.
11. On terminal event, worker maps harness success/error deterministically (`completed` vs `failed_permanent`) and promotes outbox row for final Slack delivery.
12. Outbox sender delivers final response exactly once and marks delivered.

## Spawn Gating Workflow

1. `/agent/message` and `/agent/execute` require active `(thread_key, assignment_generation)`.
2. Missing assignment returns `409 NO_ACTIVE_ASSIGNMENT`.
3. Stale generation returns `409 ASSIGNMENT_GENERATION_STALE`.
4. Duplicate idempotency key with same request hash returns prior durable result.
5. Duplicate idempotency key with different hash returns `409 IDEMPOTENCY_PAYLOAD_MISMATCH`.

## Runtime Restart Workflow (Amp Continue)

1. Worker detects runtime loss while execution is non-terminal.
2. Worker creates/reclaims replacement runtime for the same thread assignment.
3. Worker loads pinned prompt identity from assignment generation.
4. Worker resumes conversation using persisted Amp thread identity (`amp_thread_id`) from assignment.
5. Worker replays persisted in-flight stdin snapshot for current execution attempt.
6. Execution remains under same `execution_id`; attempts increment in `agent_execution_attempts`.

## Stream Disconnect Workflow (Slack UX vs Correctness)

1. SSE disconnects are treated as UX degradation, not correctness failure.
2. SlackBot may reconnect to `/agent/threads/{thread_key}/events` for live updates.
3. If live stream recovery fails, durable outbox still guarantees final Slack answer.
4. Slack stream state errors (for example `message_not_in_streaming_state`) never block final-delivery outbox processing.

## 24h Inactivity Shutdown Workflow

1. Reconciler scans active assignments/runtimes for `last_active_at < now() - interval '24 hours'`.
2. Matching runtime is stopped and runtime state transitions to `stopped`.
3. Active assignment is released or superseded according to policy.
4. Thread remains fully resumable by new `/agent/spawn` with incremented generation.

## Persona Workflow

1. API accepts `persona_id` on spawn.
2. Persona resolver loads prompt template from DB and computes canonical prompt hash.
3. Optional `agents_md_override` is normalized, hashed, and persisted with assignment generation.
4. Runtime boot always injects effective prompt tied to assignment generation.
5. Replays/restarts must reuse same prompt identity for that active generation.

## Final Delivery Workflow (Exactly Once)

1. Outbox row is created at execute enqueue time with `awaiting_terminal`.
2. Terminalization updates row to `pending` with final payload snapshot.
3. Delivery worker sends final Slack message idempotently using `execution_id` key.
4. Success marks outbox `delivered`; retries use backoff and jitter.
5. Exhausted retries move row to `dead_letter` with durable failure metadata and alert hooks.

## Workflows This Unlocks

1. Reliable long-running Slack tasks that always end with a final response even across restarts.
2. Scheduled/cron execution producers that write `/agent/message` + `/agent/execute` without bespoke runtime logic.
3. Zero-downtime API deploys because correctness is DB-owned, not in-memory.
4. Deterministic replay/debug of every execution attempt from durable stdin/stdout history.
