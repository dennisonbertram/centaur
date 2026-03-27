# Agent Runtime API Spec (V1)

## Scope

This spec defines every API for the redesigned durable runtime system.

1. `POST /agent/spawn`
2. `POST /agent/message`
3. `POST /agent/execute`
4. `GET /agent/executions/{execution_id}`
5. `GET /agent/threads/{thread_key}/executions`
6. `GET /agent/threads/{thread_key}/events` (SSE)
7. `POST /agent/executions/{execution_id}/cancel`
8. `POST /agent/threads/{thread_key}/release`
9. `POST /agent/final-deliveries/claim`
10. `POST /agent/final-deliveries/{execution_id}/delivered`
11. `POST /agent/final-deliveries/{execution_id}/failed`
12. `GET /healthz`
13. `GET /readyz`

These APIs assume Postgres is the durable source of truth and API servers are stateless routers.

## Common Conventions

### Authentication And Authorization

1. All `/agent/*` endpoints require bearer auth.
2. `POST /agent/spawn` requires privileged scope (for example `agent:spawn`).
3. `GET /agent/threads/{thread_key}/events` is internal and should be restricted to trusted callers (SlackBot, worker tooling).

### Authorization Scoping Rules

1. Tokens are authorized per tenant/workspace (for Slack, usually `team_id`).
2. Read endpoints must verify caller access to the target `thread_key` tenant before returning metadata.
3. `GET /agent/executions/{execution_id}` must authorize using execution's resolved `thread_key`, not only raw execution id possession.
4. `POST /agent/threads/{thread_key}/release` requires privileged scope (for example `agent:spawn` or `agent:release`).

### Minimal Validation Policy

API only validates envelopes and safety bounds:

1. Required fields exist.
2. JSON parses.
3. UTF-8 and size limits are valid.
4. Idempotency keys are present and bounded.
5. Platform-required delivery fields are present.

All orchestration semantics are enforced durably in Postgres state machines.

### Postgres Procedure Authority

1. API handlers must call authoritative DB procedures for all writes (`spawn`, `message`, `execute`, `cancel`, `release`).
2. API handlers must not implement orchestration races in process memory.
3. Assignment state transitions, idempotency conflict detection, and terminalization decisions are DB-owned outcomes.
4. Rolling API deploys are safe because request correctness does not depend on API instance-local state.

### Spawn Gating (Required)

1. `/agent/message` and `/agent/execute` are valid only when the thread has an active spawn assignment.
2. Callers must pass `assignment_generation` from the latest successful `/agent/spawn` response.
3. If no active assignment exists, APIs return `409 NO_ACTIVE_ASSIGNMENT`.
4. If `assignment_generation` is stale/mismatched, APIs return `409 ASSIGNMENT_GENERATION_STALE`.

### Execution Status Contract

`execution.status` is one of:

1. `queued`
2. `claimed`
3. `running`
4. `retry_wait`
5. `cancel_requested`
6. `completed`
7. `failed_permanent`
8. `cancelled`

### Execution Watchdog Contract

1. Each accepted execution tracks durable `last_progress_at`, `silence_deadline_at`, and `hard_deadline_at` timestamps.
2. Progress is updated only when durable stdout events or durable stdin checkpoints are written.
3. If `silence_deadline_at` is breached, execution is forced to deterministic terminal handling and final delivery still proceeds.
4. If `hard_deadline_at` is breached, execution is force-terminalized (`failed_permanent` or `cancelled` by policy) and final delivery still proceeds.

### Identifier Contract

1. `spawn_id`, `message_id`, `execute_id`, and `release_id` are caller-chosen idempotency keys scoped to `thread_key`.
2. `execution_id` is server-generated and is the canonical durable identifier for one execution request.
3. Status and cancel operations address executions by `execution_id`.
4. Read responses that include execution records return both `execution_id` and `execute_id`.
5. This API does not expose or require `turn_id`/`turn_command` fields.

### Content Types

1. JSON requests use `Content-Type: application/json`.
2. SSE responses use `Content-Type: text/event-stream`.

### Idempotency

1. `/agent/spawn` idempotency key: `(thread_key, spawn_id)`.
2. `/agent/message` idempotency key: `(thread_key, message_id)`.
3. `/agent/execute` idempotency key: `(thread_key, execute_id)`.
4. Duplicate idempotent writes return `200`/`202` with existing durable identifiers.

### Idempotency Precedence Rules

1. Server checks idempotency key before spawn-gating checks.
2. If an existing row is found and request payload hash matches, return existing durable response even if assignment was later superseded.
3. If idempotency key exists but payload hash differs, return `409 IDEMPOTENCY_PAYLOAD_MISMATCH`.
4. Only brand-new writes must pass active-assignment generation checks.

### Request Hash Canonicalization

1. Server computes `request_hash` from RFC 8785 JSON Canonicalization Scheme (JCS) form of the write payload (excluding transient metadata like `request_id`).
2. Canonicalization is stable across key order and whitespace differences.
3. `request_hash` is stored durably and used for idempotency payload mismatch detection.

### Amp JSON Compatibility Guarantee

1. `/agent/message.event` accepts Amp-compatible message envelopes and content blocks.
2. Inline `image`/`document` blocks are accepted at ingress, then durably rewritten to `attachment_ref` storage.
3. Worker writes runtime stdin as Amp NDJSON only (`--stream-json-input` contract).
4. Runtime stdout is durably persisted before projection, including thinking blocks/deltas.
5. SSE `amp_raw_event` payloads represent persisted raw Amp events without lossy normalization.

### Error Envelope

```json
{
  "ok": false,
  "error": {
    "code": "NO_ACTIVE_ASSIGNMENT",
    "message": "No active runtime assignment for thread_key",
    "retryable": true,
    "details": {
      "thread_key": "slack:C123:1742912345.000100"
    }
  },
  "request_id": "req_01H..."
}
```

### Standard Error Codes

1. `INVALID_ARGUMENT` (`400`)
2. `UNAUTHENTICATED` (`401`)
3. `FORBIDDEN` (`403`)
4. `NOT_FOUND` (`404`)
5. `CONFLICT` (`409`)
6. `UNPROCESSABLE_ENTITY` (`422`)
7. `TOO_MANY_REQUESTS` (`429`)
8. `SERVICE_UNAVAILABLE` (`503`)

Common domain error codes returned in `error.code`:

1. `NO_ACTIVE_ASSIGNMENT`
2. `ASSIGNMENT_GENERATION_STALE`
3. `IDEMPOTENCY_PAYLOAD_MISMATCH`
4. `THREAD_AFFINITY_VIOLATION`
5. `RUNTIME_CAPACITY_EXHAUSTED`
6. `ACTIVE_ASSIGNMENT_PROMPT_MISMATCH`
7. `STREAM_RANGE_GONE`
8. `INVALID_RELEASE_FLAGS`

## API: `POST /agent/spawn`

Purpose: pin a warm runtime to one thread and resolve prompt identity.

### Request

```json
{
  "thread_key": "slack:C123:1742912345.000100",
  "spawn_id": "slack:T123:Ev123ABC456:spawn",
  "harness": "amp",
  "persona_id": "prs_policy_default",
  "agents_md_override": null,
  "delivery": {
    "platform": "slack",
    "team_id": "T123",
    "channel": "C123",
    "thread_ts": "1742912345.000100"
  },
  "metadata": {
    "source": "slackbot"
  }
}
```

### Response (`200`)

```json
{
  "ok": true,
  "runtime_id": "rtm_3f5e...",
  "thread_key": "slack:C123:1742912345.000100",
  "assignment_state": "assigned_idle",
  "assignment_generation": 12,
  "persona_id": "prs_policy_default",
  "prompt_ref": "persona:policy_default@v4",
  "effective_agents_md_sha256": "d88f..."
}
```

### Semantics

1. Prompt resolution precedence is `agents_md_override -> persona_id -> internal prompt_ref -> default`.
2. If active assignment exists for `thread_key` and resolved prompt identity matches, return existing assignment.
3. If active assignment exists for `thread_key` and resolved prompt identity differs, return `409 ACTIVE_ASSIGNMENT_PROMPT_MISMATCH`.
4. Else claim one unassigned warm runtime (or create new runtime) and assign.
5. Runtime affinity is strict: one live runtime cannot be reassigned across threads.
6. Spawn never mutates an existing active assignment in-place; callers must release first to force a new assignment generation.
7. Duplicate `(thread_key, spawn_id)` returns existing durable row when request hash matches.

### Errors

1. `422 UNKNOWN_PERSONA_ID`
2. `422 DISABLED_PERSONA_ID`
3. `403 PERSONA_NOT_ALLOWED`
4. `409 ASSIGNMENT_CONFLICT`
5. `503 RUNTIME_CAPACITY_EXHAUSTED`
6. `409 ACTIVE_ASSIGNMENT_PROMPT_MISMATCH`

## API: `POST /agent/message`

Purpose: append one durable transcript event against an active spawn assignment.

### Request

```json
{
  "thread_key": "slack:C123:1742912345.000100",
  "assignment_generation": 12,
  "message_id": "slack:T123:Ev123ABC456:message",
  "event": {
    "type": "user",
    "message": {
      "role": "user",
      "content": [
        { "type": "text", "text": "what do you see?" },
        {
          "type": "image",
          "source_path": "file:///Users/alice/images/example.jpg",
          "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": "..."
          }
        }
      ]
    }
  },
  "metadata": {
    "platform": "slack",
    "team_id": "T123",
    "channel": "C123",
    "thread_ts": "1742912345.000100",
    "slack_event_id": "Ev123ABC456"
  }
}
```

### Response (`200`)

```json
{
  "ok": true,
  "message_id": "slack:T123:Ev123ABC456:message",
  "stored_event_id": "msg_evt_01H...",
  "attachment_ids": ["att_01", "att_02"]
}
```

### Semantics

1. Active assignment is required for `thread_key` and must match `assignment_generation`.
2. Inline multimodal blocks are accepted.
3. Binary payloads are extracted and persisted to `attachments`.
4. Stored transcript is rewritten to `attachment_ref` for non-text blocks.
5. Execution must always resolve bytes from `attachments`.
6. Duplicate `(thread_key, message_id)` returns existing durable row when request hash matches.

### Errors

1. `400 INVALID_AMP_EVENT_ENVELOPE`
2. `422 ATTACHMENT_BYTES_REQUIRED`
3. `422 INVALID_BASE64_ATTACHMENT`
4. `413 PAYLOAD_TOO_LARGE`
5. `409 NO_ACTIVE_ASSIGNMENT`
6. `409 ASSIGNMENT_GENERATION_STALE`
7. `409 IDEMPOTENCY_PAYLOAD_MISMATCH`

## API: `POST /agent/execute`

Purpose: enqueue one durable execution request.

### Request

```json
{
  "thread_key": "slack:C123:1742912345.000100",
  "assignment_generation": 12,
  "execute_id": "slack:T123:Ev123ABC456:execute",
  "harness": "amp",
  "delivery": {
    "platform": "slack",
    "team_id": "T123",
    "channel": "C123",
    "thread_ts": "1742912345.000100",
    "recipient_user_id": "U123",
    "recipient_team_id": "T123"
  },
  "metadata": {
    "source": "slackbot"
  }
}
```

### Response (`202`)

```json
{
  "ok": true,
  "execution_id": "exe_01H...",
  "execute_id": "slack:T123:Ev123ABC456:execute",
  "assignment_generation": 12,
  "status": "queued",
  "final_key": "final:slack:C123:1742912345.000100:exe_01H...",
  "delivery_token": "dlv_01H..."
}
```

### Semantics

1. Active assignment is required for `thread_key` and must match `assignment_generation`.
2. API persists request and returns fast.
3. Worker serializes execution per `thread_key`.
4. Retries use the same `execution_id` with incremented attempt number.
5. Enqueue transaction also creates one durable final-delivery obligation row in `awaiting_terminal` state.
6. Final Slack delivery dedupe key is `thread_key + execution_id + final`.
7. Duplicate `(thread_key, execute_id)` returns existing durable row when request hash matches.

### Errors

1. `409 NO_ACTIVE_ASSIGNMENT`
2. `409 ASSIGNMENT_GENERATION_STALE`
3. `409 THREAD_AFFINITY_VIOLATION`
4. `422 INVALID_DELIVERY_SHAPE`
5. `409 IDEMPOTENCY_PAYLOAD_MISMATCH`

## API: `GET /agent/executions/{execution_id}`

Purpose: fetch durable execution status and final result projection.

Authorization: caller must be authorized for the execution's resolved tenant/thread scope.

### Response (`200`)

```json
{
  "ok": true,
  "execution": {
    "execution_id": "exe_01H...",
    "execute_id": "slack:T123:Ev123ABC456:execute",
    "thread_key": "slack:C123:1742912345.000100",
    "assignment_generation": 12,
    "status": "running",
    "attempt": 2,
    "created_at": "2026-03-26T10:00:00Z",
    "updated_at": "2026-03-26T10:00:04Z",
    "terminal": null
  }
}
```

Terminal example:

```json
{
  "ok": true,
  "execution": {
    "execution_id": "exe_01H...",
    "execute_id": "slack:T123:Ev123ABC456:execute",
    "thread_key": "slack:C123:1742912345.000100",
    "assignment_generation": 12,
    "status": "completed",
    "attempt": 2,
    "terminal": {
      "completed_at": "2026-03-26T10:00:08Z",
      "result_text": "Final answer",
      "stop_reason": "end_turn"
    }
  }
}
```

## API: `GET /agent/threads/{thread_key}/executions`

Purpose: list execution requests for a thread.

Authorization: caller must be authorized for the target thread tenant scope.

### Query Params

1. `limit` (default `50`, max `200`)
2. `cursor` (opaque pagination cursor)

### Response (`200`)

```json
{
  "ok": true,
  "items": [
    {
      "execution_id": "exe_01H...",
      "execute_id": "slack:T123:Ev123ABC456:execute",
      "assignment_generation": 12,
      "status": "completed",
      "created_at": "2026-03-26T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

## API: `GET /agent/threads/{thread_key}/events` (SSE)

Purpose: replayable event stream for SlackBot or internal consumers.

Authorization: restricted internal use; caller must be authorized for thread scope.

### Query Params

1. `from_seq` (optional, default `latest+1` for tail mode)
2. `execution_id` (optional filter; required for durable SlackBot execution-scoped sessions)
3. `kinds` (optional comma-separated filter)

### Headers

1. Supports `Last-Event-ID` for resume.
2. Server returns `Cache-Control: no-cache`.

### Cursor Semantics

1. `from_seq` is inclusive (the first sequence number that may be emitted).
2. If `Last-Event-ID` is present, it takes precedence over `from_seq` and resume starts at `Last-Event-ID + 1`.
3. If neither is provided, server enters tail mode from `latest+1`.

### SSE Event

```text
id: 1287
event: agent_event
data: {"seq":1287,"thread_key":"slack:C123:1742912345.000100","execution_id":"exe_01H...","attempt_id":"att_2","kind":"amp_raw_event","payload":{"type":"assistant","message":{"role":"assistant","content":[{"type":"thinking","thinking":"..."}]}}}

```

### Guarantees

1. `seq` is monotonic and durable.
2. Reconnect from `from_seq` replays missed events.
3. Event stream liveness is not required for execution correctness.
4. Server emits heartbeat comments (for example every 15s) to keep intermediaries from timing out idle streams.
5. If `from_seq` is older than retained history, server returns `410 STREAM_RANGE_GONE`.

## API: `POST /agent/executions/{execution_id}/cancel`

Purpose: request cancellation of a queued or running execution.

Authorization: caller must be authorized for the execution's resolved tenant/thread scope.

### Request

```json
{
  "reason": "user_requested"
}
```

### Response (`202`)

```json
{
  "ok": true,
  "execution_id": "exe_01H...",
  "status": "cancel_requested"
}
```

### Semantics

1. If queued, execution transitions directly to terminal `cancelled`.
2. If running, execution transitions to durable `cancel_requested`, worker interrupts attempt, then marks terminal `cancelled`.
3. Cancel is idempotent; repeated calls return current execution status.
4. Final delivery still emits one deterministic terminal message/update.

## API: `POST /agent/threads/{thread_key}/release`

Purpose: release active thread assignment and optionally stop the pinned runtime.

### Request

```json
{
  "release_id": "slack:T123:Ev123ABC456:release",
  "assignment_generation": 12,
  "reason": "thread_closed",
  "stop_runtime": true,
  "cancel_non_terminal_executions": true
}
```

### Response (`200`)

```json
{
  "ok": true,
  "thread_key": "slack:C123:1742912345.000100",
  "assignment_generation": 12,
  "released": true,
  "runtime_stopped": true,
  "cancelled_execution_count": 1
}
```

### Semantics

1. Release is idempotent by `(thread_key, release_id)`.
2. Active assignment for `(thread_key, assignment_generation)` transitions to `released`.
3. If `cancel_non_terminal_executions=true`, queued/running executions for that generation are moved to terminal `cancelled` deterministically.
4. If `cancel_non_terminal_executions=false`, already queued/running executions for that generation continue, but new message/execute writes are rejected as stale.
5. `stop_runtime=true` is valid only when there are no non-terminal executions remaining for that generation.
6. If `stop_runtime=true` with non-terminal executions and `cancel_non_terminal_executions=false`, return `422 INVALID_RELEASE_FLAGS`.
7. After release, message/execute calls for that generation fail with `409 ASSIGNMENT_GENERATION_STALE`.
8. A subsequent successful `/agent/spawn` for that thread yields a new `assignment_generation`.
9. Continuing executions after release are authorized by their persisted `(thread_key, assignment_generation)` snapshot, not by current active-assignment state.

### Errors

1. `409 NO_ACTIVE_ASSIGNMENT`
2. `409 ASSIGNMENT_GENERATION_STALE`
3. `403 FORBIDDEN`
4. `422 INVALID_RELEASE_FLAGS`

## API: `POST /agent/final-deliveries/claim`

Purpose: lease terminal delivery obligations to a delivery worker (SlackBot consumer).

### Request

```json
{
  "consumer_id": "slackbot:prod-1",
  "limit": 20,
  "lease_seconds": 60
}
```

### Response (`200`)

```json
{
  "ok": true,
  "deliveries": [
    {
      "execution_id": "exe_01H...",
      "thread_key": "slack:C123:1742912345.000100",
      "delivery": { "platform": "slack", "channel": "C123", "thread_ts": "1742912345.000100" },
      "final_payload": {
        "execution_id": "exe_01H...",
        "status": "completed",
        "result_text": "Final answer"
      },
      "attempt_count": 1,
      "lease_expires_at": "2026-03-26T10:00:10Z"
    }
  ]
}
```

### Semantics

1. Claims only rows in `pending` or due `retry_wait` state.
2. Claim sets `state='sending'`, increments `attempt_count`, and applies a lease (`lease_owner`, `lease_expires_at`).
3. Claims are ordered by `next_attempt_at` then `created_at`.
4. Rows with non-expired lease owned by another consumer are skipped.

## API: `POST /agent/final-deliveries/{execution_id}/delivered`

Purpose: ack successful final delivery for one execution.

### Request

```json
{
  "consumer_id": "slackbot:prod-1"
}
```

### Response (`200`)

```json
{
  "ok": true,
  "execution_id": "exe_01H...",
  "state": "delivered"
}
```

### Semantics

1. Caller must hold the active lease (or row is already terminal idempotently).
2. Success sets `state='delivered'`, clears lease fields, and stamps `delivered_at`.

## API: `POST /agent/final-deliveries/{execution_id}/failed`

Purpose: report failed delivery attempt and schedule retry/backoff.

### Request

```json
{
  "consumer_id": "slackbot:prod-1",
  "error": "message_not_in_streaming_state",
  "retryable": true
}
```

### Response (`200`)

```json
{
  "ok": true,
  "execution_id": "exe_01H...",
  "state": "retry_wait",
  "next_attempt_at": "2026-03-26T10:00:40Z"
}
```

### Semantics

1. Retryable failures move row to `retry_wait` with backoff and cleared lease.
2. Non-retryable failures move row to `dead_letter` with failure metadata.
3. Reporting failure is idempotent for already terminal outbox states.

## API: `GET /healthz`

Purpose: process liveness.

### Response (`200`)

```json
{ "ok": true }
```

## API: `GET /readyz`

Purpose: readiness for serving traffic.

### Response (`200`)

```json
{
  "ok": true,
  "checks": {
    "postgres": "ok",
    "migrations": "ok",
    "schema_compatibility": "ok",
    "runtime_credentials": "ok"
  }
}
```

Failure example (`503`):

```json
{
  "ok": false,
  "checks": {
    "postgres": "ok",
    "migrations": "ok",
    "schema_compatibility": "failed",
    "schema_error": "sandbox_sessions_state_check missing required state: suspended"
  }
}
```

Readiness semantics:

1. `schema_compatibility` validates required runtime assumptions (required enum/check states, required columns/indexes used by serving code).
2. Incompatible schema returns `503` so broken code/schema combinations never serve traffic.
3. When `RUNTIME_CREDENTIAL_GUARD_ENABLED=1`, readiness validates required runtime secrets via firewall health endpoints and returns `503` on missing keys.

## SlackBot Call Sequence (Deterministic)

1. Receive Slack event, verify signature, dedupe on `event_id`, ack within 3 seconds.
2. `POST /agent/spawn` with `spawn_id = slack:{team_id}:{event_id}:spawn`.
3. Read `assignment_generation` from spawn response.
4. `POST /agent/message` with `message_id = slack:{team_id}:{event_id}:message` and that `assignment_generation`.
5. `POST /agent/execute` with `execute_id = slack:{team_id}:{event_id}:execute` and that `assignment_generation`.
6. Consume `GET /agent/threads/{thread_key}/events` and map to Slack `chat.startStream`/`appendStream`/`stopStream`.
7. Rely on durable final-delivery outbox for correctness.

Optional cleanup:

1. Call `POST /agent/threads/{thread_key}/release` with `release_id = slack:{team_id}:{event_id}:release` when thread is explicitly closed or long-term parking is desired.

## Final Delivery Reconciliation

1. Every final Slack write includes deterministic metadata token (`final_key`, `execution_id`, `delivery_token`).
2. If delivery attempt outcome is unknown (timeout/network drop after send), reconciler queries thread history for that token before retry.
3. Retry is allowed only when reconciliation finds no prior delivery token match.

## Slack Stream API Constraints

1. For channel-thread streaming, `recipient_user_id` and `recipient_team_id` are required by `chat.startStream`.
2. Each `markdown_text` value sent to Slack stream APIs must be capped to 12,000 characters.
3. `chat.stopStream` should include deterministic metadata (`final_key`, `execution_id`, `delivery_token`) when possible.
4. If stream finalization cannot carry metadata and fallback path is used, send equivalent metadata on fallback final write.

## Non-Goals

1. No direct client-to-container socket attach API.
2. No correctness dependency on API process memory.
3. No runtime-only state required to recover execution.

## Legacy Endpoint Policy

1. `POST /agent/connect` and `POST /agent/reconnect` are deprecated and not part of V1.
2. By default they return `410 LEGACY_ENDPOINT_REMOVED`.
3. Temporary fallback can be enabled explicitly via `LEGACY_AGENT_WIRE_API_ENABLED=1`.
