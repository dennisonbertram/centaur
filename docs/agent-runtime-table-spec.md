# Agent Runtime Postgres Table Spec (V1)

## Design Principles

1. Postgres is the durable control plane.
2. API servers are stateless and use DB state transitions.
3. DB constraints prevent orchestration footguns.
4. Runtime processes are disposable; state must be recoverable from tables.
5. Execution of multimodal content always resolves bytes from `agent_attachments`.
6. Request hashes use RFC 8785 JCS canonicalization before hashing.

## Enum Types

```sql
CREATE TYPE agent_execution_status AS ENUM (
  'queued',
  'claimed',
  'running',
  'retry_wait',
  'cancel_requested',
  'completed',
  'failed_permanent',
  'cancelled'
);

CREATE TYPE agent_attempt_status AS ENUM (
  'started',
  'running',
  'succeeded',
  'retryable_failed',
  'failed_permanent',
  'cancelled'
);

CREATE TYPE agent_runtime_state AS ENUM (
  'starting',
  'ready',
  'busy',
  'idle',
  'lost',
  'stopped',
  'quarantined'
);

CREATE TYPE agent_assignment_state AS ENUM (
  'assigned_idle',
  'assigned_busy',
  'released',
  'superseded'
);

CREATE TYPE agent_stream_state AS ENUM (
  'not_started',
  'starting',
  'streaming',
  'degraded',
  'stopping',
  'finalized'
);

CREATE TYPE agent_delivery_state AS ENUM (
  'awaiting_terminal',
  'pending',
  'sending',
  'retry_wait',
  'delivered',
  'dead_letter'
);

CREATE TYPE agent_delivery_attempt_outcome AS ENUM (
  'accepted',
  'rejected',
  'unknown'
);

CREATE TYPE agent_event_kind AS ENUM (
  'amp_raw_event',
  'execution_state',
  'projection_chunk',
  'tool_update',
  'plan_update',
  'system'
);
```

## Core Tables

## `agent_threads`

Canonical thread identity and routing metadata.

```sql
CREATE TABLE agent_threads (
  thread_key TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  team_id TEXT,
  channel TEXT,
  thread_ts TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_message_at TIMESTAMPTZ,
  last_execution_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX agent_threads_slack_unique
  ON agent_threads (team_id, channel, thread_ts)
  WHERE platform = 'slack';
```

## `agent_slack_event_dedupe`

Slack webhook dedupe ledger keyed by Slack `event_id`.

```sql
CREATE TABLE agent_slack_event_dedupe (
  team_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  thread_key TEXT NOT NULL REFERENCES agent_threads(thread_key),
  payload_sha256 TEXT,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (team_id, event_id)
);
```

## `agent_messages`

Durable transcript rows from `/agent/message`.

```sql
CREATE TABLE agent_messages (
  message_row_id BIGSERIAL PRIMARY KEY,
  thread_key TEXT NOT NULL REFERENCES agent_threads(thread_key),
  assignment_generation BIGINT NOT NULL,
  message_id TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  event_json JSONB NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (thread_key, message_id),
  UNIQUE (message_row_id, thread_key)
);

CREATE INDEX agent_messages_thread_order_idx
  ON agent_messages (thread_key, message_row_id);

CREATE INDEX agent_messages_thread_generation_idx
  ON agent_messages (thread_key, assignment_generation, message_row_id);
```

`event_json` is canonical storage and must contain `attachment_ref` blocks for non-text payloads.

## `agent_attachments`

Durable attachment bytes and metadata.

```sql
CREATE TABLE agent_attachments (
  attachment_id TEXT PRIMARY KEY,
  thread_key TEXT NOT NULL REFERENCES agent_threads(thread_key),
  sha256 TEXT NOT NULL,
  media_type TEXT NOT NULL,
  byte_size BIGINT NOT NULL CHECK (byte_size > 0),
  source_path TEXT,
  file_name TEXT,
  payload BYTEA NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (attachment_id, thread_key)
);

CREATE INDEX agent_attachments_thread_created_idx
  ON agent_attachments (thread_key, created_at);

CREATE INDEX agent_attachments_sha_idx
  ON agent_attachments (sha256);
```

## `agent_message_attachment_refs`

Links each message content block to an attachment id.

```sql
CREATE TABLE agent_message_attachment_refs (
  message_row_id BIGINT NOT NULL,
  thread_key TEXT NOT NULL,
  content_index INTEGER NOT NULL,
  attachment_id TEXT NOT NULL,
  block_type TEXT NOT NULL,
  source_path TEXT,
  PRIMARY KEY (message_row_id, content_index),
  FOREIGN KEY (message_row_id, thread_key)
    REFERENCES agent_messages(message_row_id, thread_key)
    ON DELETE CASCADE,
  FOREIGN KEY (attachment_id, thread_key)
    REFERENCES agent_attachments(attachment_id, thread_key)
);

CREATE INDEX agent_message_attachment_refs_attachment_idx
  ON agent_message_attachment_refs (attachment_id);
```

## `agent_execution_requests`

Durable execute intents from `/agent/execute`.

```sql
CREATE TABLE agent_execution_requests (
  execution_id TEXT PRIMARY KEY,
  thread_key TEXT NOT NULL REFERENCES agent_threads(thread_key),
  assignment_generation BIGINT NOT NULL,
  execute_id TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  harness TEXT NOT NULL DEFAULT 'amp',
  status agent_execution_status NOT NULL,
  delivery JSONB NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  queue_seq BIGSERIAL NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  claimed_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  last_progress_at TIMESTAMPTZ,
  silence_deadline_at TIMESTAMPTZ,
  hard_deadline_at TIMESTAMPTZ,
  stream_break_count INTEGER NOT NULL DEFAULT 0,
  last_stream_break_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  terminal_reason TEXT,
  result_text TEXT,
  result_json JSONB,
  current_attempt INTEGER NOT NULL DEFAULT 0,
  UNIQUE (thread_key, execute_id),
  UNIQUE (queue_seq),
  UNIQUE (execution_id, thread_key),
  UNIQUE (execution_id, thread_key, assignment_generation)
);

CREATE INDEX agent_execution_requests_thread_queue_idx
  ON agent_execution_requests (thread_key, queue_seq);

CREATE INDEX agent_execution_requests_thread_generation_idx
  ON agent_execution_requests (thread_key, assignment_generation, queue_seq);

CREATE INDEX agent_execution_requests_status_idx
  ON agent_execution_requests (status, created_at);

CREATE INDEX agent_execution_requests_watchdog_idx
  ON agent_execution_requests (status, silence_deadline_at, hard_deadline_at)
  WHERE status IN ('running', 'claimed');
```

## `agent_execution_attempts`

Per-attempt execution details for retries/recovery.

```sql
CREATE TABLE agent_execution_attempts (
  attempt_id TEXT PRIMARY KEY,
  execution_id TEXT NOT NULL,
  thread_key TEXT NOT NULL REFERENCES agent_threads(thread_key),
  attempt_no INTEGER NOT NULL,
  runtime_id TEXT,
  assignment_generation BIGINT NOT NULL,
  status agent_attempt_status NOT NULL,
  amp_thread_id TEXT,
  stdin_manifest_sha256 TEXT,
  failure_code TEXT,
  failure_message TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at TIMESTAMPTZ,
  UNIQUE (execution_id, attempt_no),
  FOREIGN KEY (execution_id, thread_key, assignment_generation)
    REFERENCES agent_execution_requests(execution_id, thread_key, assignment_generation)
    ON DELETE CASCADE
);

CREATE INDEX agent_execution_attempts_execution_idx
  ON agent_execution_attempts (execution_id, attempt_no);

CREATE UNIQUE INDEX agent_execution_attempts_one_active_per_thread_idx
  ON agent_execution_attempts (thread_key)
  WHERE status IN ('started', 'running');
```

The partial unique index above enforces strict per-thread serialization at the DB layer.

## `agent_execution_stdin_lines`

Exact stdin snapshot for deterministic replay.

```sql
CREATE TABLE agent_execution_stdin_lines (
  attempt_id TEXT NOT NULL REFERENCES agent_execution_attempts(attempt_id) ON DELETE CASCADE,
  line_no INTEGER NOT NULL,
  line_json JSONB NOT NULL,
  PRIMARY KEY (attempt_id, line_no)
);
```

## Runtime And Assignment Tables

## `agent_runtimes`

Runtime/container lifecycle and lease metadata.

```sql
CREATE TABLE agent_runtimes (
  runtime_id TEXT PRIMARY KEY,
  harness TEXT NOT NULL,
  state agent_runtime_state NOT NULL,
  container_ref TEXT,
  host_node TEXT,
  lease_owner TEXT,
  lease_expires_at TIMESTAMPTZ,
  last_active_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_amp_thread_id TEXT,
  prompt_sha256 TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  stopped_at TIMESTAMPTZ
);

CREATE INDEX agent_runtimes_state_activity_idx
  ON agent_runtimes (state, last_active_at);
```

`last_seen_amp_thread_id` is diagnostic/runtime cache only. Authoritative continue identity is stored on assignment generation rows.

## `agent_runtime_assignments`

Thread affinity and prompt identity binding.

```sql
CREATE TABLE agent_runtime_assignments (
  assignment_id TEXT PRIMARY KEY,
  runtime_id TEXT NOT NULL REFERENCES agent_runtimes(runtime_id),
  thread_key TEXT NOT NULL REFERENCES agent_threads(thread_key),
  spawn_id TEXT NOT NULL,
  spawn_request_hash TEXT NOT NULL,
  assignment_generation BIGINT NOT NULL,
  state agent_assignment_state NOT NULL,
  persona_id TEXT,
  prompt_ref TEXT,
  effective_agents_md_sha256 TEXT NOT NULL,
  agents_md_override_ciphertext BYTEA,
  amp_thread_id TEXT,
  amp_thread_updated_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  released_at TIMESTAMPTZ,
  UNIQUE (thread_key, spawn_id),
  UNIQUE (thread_key, assignment_generation)
);

CREATE UNIQUE INDEX agent_runtime_assignments_one_active_per_runtime_idx
  ON agent_runtime_assignments (runtime_id)
  WHERE state IN ('assigned_idle', 'assigned_busy');

CREATE UNIQUE INDEX agent_runtime_assignments_one_active_per_thread_idx
  ON agent_runtime_assignments (thread_key)
  WHERE state IN ('assigned_idle', 'assigned_busy');
```

## `agent_assignment_releases`

Idempotent release ledger for `POST /agent/threads/{thread_key}/release`.

```sql
CREATE TABLE agent_assignment_releases (
  release_row_id BIGSERIAL PRIMARY KEY,
  thread_key TEXT NOT NULL REFERENCES agent_threads(thread_key),
  release_id TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  assignment_generation BIGINT NOT NULL,
  reason TEXT,
  stop_runtime BOOLEAN NOT NULL DEFAULT true,
  cancel_non_terminal_executions BOOLEAN NOT NULL DEFAULT true,
  cancelled_execution_count INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (thread_key, release_id),
  FOREIGN KEY (thread_key, assignment_generation)
    REFERENCES agent_runtime_assignments(thread_key, assignment_generation)
);
```

DB trigger rule: `thread_key` is immutable for active assignments; cross-thread reassignment requires release + new assignment row.

DB trigger rule: inserts into `agent_messages` and `agent_execution_requests` must reference an active assignment row for `(thread_key, assignment_generation)`.

DB trigger rule: release transitions assignment state to `released` and atomically terminalizes non-terminal execution requests for that generation when configured.

DB worker rule: if release is called with `cancel_non_terminal_executions=false`, workers may continue processing already-enqueued execution rows for that `(thread_key, assignment_generation)` snapshot.

Recommended FK constraints (added after `agent_runtime_assignments` exists):

```sql
ALTER TABLE agent_messages
  ADD CONSTRAINT agent_messages_assignment_fk
  FOREIGN KEY (thread_key, assignment_generation)
  REFERENCES agent_runtime_assignments(thread_key, assignment_generation);

ALTER TABLE agent_execution_requests
  ADD CONSTRAINT agent_execution_requests_assignment_fk
  FOREIGN KEY (thread_key, assignment_generation)
  REFERENCES agent_runtime_assignments(thread_key, assignment_generation);
```

## Authoritative Write Procedures

All app writes should go through stored procedures to eliminate race ambiguity.

`agent_append_message(...)` and `agent_enqueue_execution(...)` must apply idempotency before assignment-gating checks.

First, idempotency lookup by `(thread_key, message_id)` or `(thread_key, execute_id)`:

```sql
-- message path
SELECT request_hash, message_row_id AS durable_id
FROM agent_messages
WHERE thread_key = p_thread_key
  AND message_id = p_message_id
FOR UPDATE;

-- execute path
SELECT request_hash, execution_id AS durable_id
FROM agent_execution_requests
WHERE thread_key = p_thread_key
  AND execute_id = p_execute_id
FOR UPDATE;
```

If no idempotency row exists, perform assignment-gating lock/check:

```sql
SELECT assignment_id, state
FROM agent_runtime_assignments
WHERE thread_key = p_thread_key
  AND assignment_generation = p_assignment_generation
FOR UPDATE;
```

Then enforce deterministic outcomes:

1. Idempotency row exists with same request hash -> return existing durable row.
2. Idempotency row exists with different request hash -> `IDEMPOTENCY_PAYLOAD_MISMATCH`.
3. No assignment row for thread -> `NO_ACTIVE_ASSIGNMENT`.
4. Assignment exists for thread but different generation is active -> `ASSIGNMENT_GENERATION_STALE`.
5. Assignment exists for generation but state is not active (`released`/`superseded`) -> `ASSIGNMENT_GENERATION_STALE`.
6. Otherwise insert new row.

`agent_spawn_assign(...)` and `agent_release_assignment(...)` follow the same idempotency-hash rule:

1. Existing idempotency row + same hash -> return existing durable result.
2. Existing idempotency row + different hash -> `IDEMPOTENCY_PAYLOAD_MISMATCH`.

`agent_release_assignment(...)` must also enforce release-flag determinism:

1. If `stop_runtime=true` and non-terminal executions exist for target generation while `cancel_non_terminal_executions=false`, return `INVALID_RELEASE_FLAGS`.
2. If `cancel_non_terminal_executions=true`, terminalize queued/running executions for target generation as `cancelled` in the same transaction.
3. If `cancel_non_terminal_executions=false`, mark assignment `released` but do not accept new writes for that generation.

## Event, Stream, And Delivery Tables

## `agent_runtime_events`

Durable raw and projected event log (SSE source of truth).

```sql
CREATE TABLE agent_runtime_events (
  seq BIGSERIAL PRIMARY KEY,
  thread_key TEXT NOT NULL REFERENCES agent_threads(thread_key),
  execution_id TEXT,
  assignment_generation BIGINT,
  attempt_id TEXT REFERENCES agent_execution_attempts(attempt_id) ON DELETE CASCADE,
  runtime_id TEXT REFERENCES agent_runtimes(runtime_id),
  kind agent_event_kind NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (
    (execution_id IS NULL AND assignment_generation IS NULL) OR
    (execution_id IS NOT NULL AND assignment_generation IS NOT NULL)
  ),
  FOREIGN KEY (execution_id, thread_key, assignment_generation)
    REFERENCES agent_execution_requests(execution_id, thread_key, assignment_generation)
    ON DELETE CASCADE
);

CREATE INDEX agent_runtime_events_thread_seq_idx
  ON agent_runtime_events (thread_key, seq);

CREATE INDEX agent_runtime_events_execution_seq_idx
  ON agent_runtime_events (execution_id, seq);
```

## `agent_stream_sessions`

Consumer cursor and stream state (for SlackBot reconnection).

This table stores execution-scoped durable stream sessions; ad-hoc thread-wide debug streams can be served without persisting a session row.

```sql
CREATE TABLE agent_stream_sessions (
  stream_session_id TEXT PRIMARY KEY,
  consumer_type TEXT NOT NULL,
  consumer_key TEXT NOT NULL,
  thread_key TEXT NOT NULL REFERENCES agent_threads(thread_key),
  execution_id TEXT NOT NULL,
  status agent_stream_state NOT NULL,
  channel TEXT,
  thread_ts TEXT,
  slack_stream_ts TEXT,
  last_emitted_seq BIGINT NOT NULL DEFAULT 0,
  started_at TIMESTAMPTZ,
  finalized_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (consumer_type, consumer_key, execution_id),
  FOREIGN KEY (execution_id, thread_key)
    REFERENCES agent_execution_requests(execution_id, thread_key)
    ON DELETE CASCADE
);
```

## `agent_final_delivery_outbox`

Exactly-once final response delivery ledger.

`delivery_token` is embedded in Slack message metadata and used for unknown-outcome reconciliation.

```sql
CREATE TABLE agent_final_delivery_outbox (
  final_key TEXT PRIMARY KEY,
  execution_id TEXT NOT NULL,
  thread_key TEXT NOT NULL,
  delivery_token TEXT NOT NULL UNIQUE,
  status agent_delivery_state NOT NULL,
  payload_markdown TEXT,
  payload_blocks JSONB,
  payload_metadata JSONB,
  terminal_snapshot_at TIMESTAMPTZ,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ,
  last_error TEXT,
  delivered_at TIMESTAMPTZ,
  slack_channel TEXT,
  slack_thread_ts TEXT,
  slack_message_ts TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (execution_id),
  FOREIGN KEY (execution_id, thread_key)
    REFERENCES agent_execution_requests(execution_id, thread_key)
    ON DELETE CASCADE
);

CREATE INDEX agent_final_delivery_outbox_status_next_idx
  ON agent_final_delivery_outbox (status, next_attempt_at);
```

Outbox lifecycle contract:

1. Row is inserted during `/agent/execute` enqueue with `status='awaiting_terminal'`.
2. Terminalization transaction sets final payload fields and moves row to `status='pending'`.
3. Delivery worker processes only `pending`/`retry_wait`; `awaiting_terminal` rows are watchdog-visible obligations.

## `agent_final_delivery_attempts`

Audit trail of every Slack final delivery try.

`outcome='unknown'` requires reconciliation by `delivery_token` lookup before retry.

```sql
CREATE TABLE agent_final_delivery_attempts (
  delivery_attempt_id BIGSERIAL PRIMARY KEY,
  final_key TEXT NOT NULL REFERENCES agent_final_delivery_outbox(final_key) ON DELETE CASCADE,
  attempt_no INTEGER NOT NULL,
  method TEXT NOT NULL,
  outcome agent_delivery_attempt_outcome NOT NULL,
  request_json JSONB,
  response_status INTEGER,
  response_json JSONB,
  retry_after_seconds INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (final_key, attempt_no)
);
```

## Persona Registry Tables

## `agent_personas`

Stable persona ids and access policy.

```sql
CREATE TABLE agent_personas (
  persona_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT true,
  default_version INTEGER NOT NULL,
  allowlist JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## `agent_persona_versions`

Versioned prompt artifacts resolved by `persona_id`.

```sql
CREATE TABLE agent_persona_versions (
  persona_id TEXT NOT NULL REFERENCES agent_personas(persona_id),
  version INTEGER NOT NULL,
  prompt_ref TEXT NOT NULL UNIQUE,
  agents_md TEXT NOT NULL,
  agents_md_sha256 TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (persona_id, version)
);

CREATE INDEX agent_persona_versions_active_idx
  ON agent_persona_versions (persona_id, active);
```

## Required DB Invariants

These are not optional and should be enforced by constraints/triggers/procedures.

1. Exactly one active assignment per thread.
2. Exactly one active assignment per runtime.
3. At most one running attempt per thread.
4. Execution terminal state is single-assignment (`completed`, `failed_permanent`, or `cancelled`).
5. Final delivery outbox has exactly one row per execution (`UNIQUE execution_id`) and is created at enqueue time.
6. Runtime assigned to thread A must never process execution for thread B (worker transaction checks assignment generation + thread key).
7. Non-text execution payloads must map to `agent_attachments` rows; missing refs fail deterministically.
8. `/agent/message` insert is rejected unless `(thread_key, assignment_generation)` maps to an active assignment.
9. `/agent/execute` insert is rejected unless `(thread_key, assignment_generation)` maps to an active assignment.
10. `agent_runtime_events` rows with `execution_id` must match execution `thread_key` + `assignment_generation`.
11. Attachment refs cannot cross threads due composite FK (`message_row_id/thread_key` and `attachment_id/thread_key`).
12. Cancel flow status transition is durable (`running -> cancel_requested -> cancelled` or `queued -> cancelled`).
13. Idempotency keys with mismatched request hash are rejected with `IDEMPOTENCY_PAYLOAD_MISMATCH`.
14. Spawn/release idempotency payload mismatch is rejected using stored spawn/release request hashes.
15. Same idempotency key + same request hash must return existing durable row even if assignment generation was later released/superseded.
16. `agent_stream_sessions.execution_id` must resolve to the same `thread_key` via composite FK.
17. Authoritative `amp_thread_id` for continue is bound to `(thread_key, assignment_generation)` in `agent_runtime_assignments`.
18. Final-delivery rows must reference the matching execution/thread pair via composite FK, not independent FKs.
19. If release does not cancel non-terminal executions, workers are still allowed to finish those rows using their persisted assignment snapshot.
20. `running`/`claimed` execution rows must carry watchdog deadlines (`silence_deadline_at`, `hard_deadline_at`).
21. Reconciler/watchdog processes rows independently and records row-level error metadata; one bad row must not block global progress.

## Idle Runtime Shutdown

Runtime sweeper query basis:

```sql
SELECT runtime_id
FROM agent_runtimes
WHERE state IN ('idle', 'ready')
  AND last_active_at < now() - interval '24 hours'
  AND NOT EXISTS (
    SELECT 1
    FROM agent_execution_attempts a
    WHERE a.runtime_id = agent_runtimes.runtime_id
      AND a.status IN ('started', 'running')
  );
```

Sweeper transitions selected runtimes to `stopped` and releases active assignments in one transaction.

## Retention And Partitioning Policy

1. `agent_runtime_events` and `agent_execution_stdin_lines` should be time-partitioned (daily or weekly).
2. Keep hot replay data for at least 30 days by default.
3. Keep `agent_attachments.payload` for at least 90 days by default; after purge, keep attachment metadata (`sha256`, `media_type`, `source_path`) for audit.
4. Never purge attachment payload rows referenced by non-terminal executions.
5. Purge jobs must be idempotent and bounded by batch size.

## Suggested Stored Procedures

To keep API stateless and reduce app-level footguns, implement these DB procedures:

1. `agent_spawn_assign(thread_key, spawn_id, request_hash, harness, persona_id, agents_md_override, delivery, metadata)`
2. `agent_append_message(thread_key, assignment_generation, message_id, request_hash, event_json, metadata)`
3. `agent_enqueue_execution(thread_key, assignment_generation, execute_id, request_hash, delivery, metadata)`
4. `agent_cancel_execution(execution_id, reason)`
5. `agent_release_assignment(thread_key, assignment_generation, release_id, request_hash, reason, stop_runtime, cancel_non_terminal_executions)`
6. `agent_mark_execution_terminal(...)`
7. `agent_schedule_final_delivery(...)`

`agent_spawn_assign(...)` must also enforce prompt-identity safety:

1. If an active assignment exists and requested prompt identity differs, return `ACTIVE_ASSIGNMENT_PROMPT_MISMATCH`.
2. Never mutate prompt identity in-place on an active assignment row.

API handlers should call procedures and return results, not implement orchestration logic in-process.
