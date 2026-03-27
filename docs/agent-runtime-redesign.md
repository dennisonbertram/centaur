# Agent Runtime Redesign (Clean Sheet)

## Intent

Design a fresh agent control plane with these hard constraints:

1. Core conversational writes are `POST /agent/message` and `POST /agent/execute`.
2. SlackBot uses `POST /agent/spawn` as the warm-runtime assignment control call.
3. Control-plane lifecycle writes include `POST /agent/threads/{thread_key}/release` and `POST /agent/executions/{execution_id}/cancel`.
4. Postgres is the production durability layer for all lifecycle management.
5. Runtime restart recovery leans on Amp Thread Continue, not container-local state.
6. Slack delivery is durable and correct under retries, crashes, and restarts.
7. Idle runtimes are shut down after 24 hours of inactivity.
8. Runtime wire protocol is Amp CLI streaming JSON input/output, including thinking blocks.
9. Orchestration is storage-agnostic so the same flow can run with an in-memory backend.
10. A warm runtime assigned to a Slack thread must never execute execution requests for any other thread.
11. System prompt must be overridable per runtime via Persona/AGENTS configuration and remain durable across restarts.
12. All binary/multimodal payloads are durably stored in `attachments` and execution always resolves from `attachments`.
13. API servers are stateless request routers; orchestration and correctness live in durable Postgres state machines.
14. Idempotent retries are deterministic via request-hash checks and never create duplicate durable work.

This design intentionally does not preserve current implementation shape.

Detailed implementation specs live in:

1. `docs/agent-runtime-api-spec.md`
2. `docs/agent-runtime-table-spec.md`
3. `docs/agent-runtime-workflows.md`

Incident evidence and data-backed requirements live in:

1. `docs/agent-runtime-incident-review-2026-03-26.md`

## Zero-Ambiguity Checklist

The redesign is only "done" when all are true in production:

1. `/agent/message` and `/agent/execute` both hard-fail with `409` unless spawn assignment exists and generation matches.
2. Every accepted `/agent/execute` row immediately creates a durable final-delivery obligation before runtime I/O begins.
3. Final Slack delivery is guaranteed from Postgres outbox workers and does not depend on live SSE connectivity.
4. Runtime stdout drops, API restarts, and container restarts all preserve correctness via durable execution state + Amp continue identity.
5. Warm runtime affinity is DB-enforced: one active runtime assignment per thread and one active thread assignment per runtime.
6. Idle shutdown policy is DB-enforced at 24h inactivity and always leaves thread state resumable via new spawn generation.
7. Readiness fails closed on schema incompatibility (required migrations, columns, and state constraints).
8. Persona resolution (`persona_id` + optional override) is pinned at spawn and immutable for the active assignment generation.
9. All multimodal execution input is reconstructed from `attachments` references, never from ephemeral container files.
10. Idempotency payload hash mismatch returns deterministic conflict (`409 IDEMPOTENCY_PAYLOAD_MISMATCH`) for all write APIs.

## Incident-Derived Non-Negotiables (2026-03-26)

These are now explicit hard requirements after production incident analysis.

1. A successful `/agent/execute` write must create a durable final-delivery obligation row immediately (before runtime work starts).
2. Streaming disconnects and reconnect loops must never be on the correctness path for final Slack completion.
3. A running execution with no durable progress beyond policy deadlines must be forced into deterministic terminal handling (`failed_permanent` or `cancelled`) and still produce exactly one final Slack response.
4. Reconciler loops must be row-isolated so one poisoned thread/session cannot block sweeps or finalization for unrelated executions.
5. Readiness must fail if required DB schema invariants are missing (for example required enum/check states), so incompatible app/schema deploys never serve traffic.
6. SlackBot may provide best-effort live UX, but final delivery correctness must be fully recoverable by background workers from Postgres alone.

## First-Principles Model

The strongest model is:

1. `POST /agent/spawn` idempotently assigns one warm runtime to one Slack thread.
2. `POST /agent/message` durably appends Amp-compatible input events to a thread transcript for an active assignment generation.
3. `POST /agent/execute` durably creates one execution request for an active assignment generation and returns `execution_id` immediately.
4. Worker claims execution requests in order, reconstructs stdin from durable transcript, and forwards to the runtime already assigned to that thread.
5. `/agent/spawn` also resolves the runtime's effective `AGENTS.md` (`persona_id` + optional override) and pins it to assignment generation.
6. Container is a dumb stdin/stdout Amp process.
7. All correctness comes from durable state and replay/continue semantics, never from open sockets.
8. SlackBot is the integration edge and consumes durable events to render streaming UX and final responses.
9. `POST /agent/threads/{thread_key}/release` is the explicit control to unpin a thread assignment and optionally cancel non-terminal work.

## Product-Level Behavior

1. Slack inbound event is acknowledged quickly and deduplicated.
2. SlackBot calls `/agent/spawn` to pin a warm runtime to the Slack thread.
3. Spawn resolves `persona_id` (and optional prompt overrides) into effective `AGENTS.md` and stores prompt identity (`persona_id`/`prompt_ref` + hash).
4. SlackBot writes `/agent/message` and then `/agent/execute` using `assignment_generation` returned by spawn.
5. Execution worker executes exactly one running execution request per thread on that thread-pinned runtime.
6. Raw Amp stdout (including thinking) is durably persisted before any projection.
7. SlackBot streams progress to Slack using native `chat.startStream` / `chat.appendStream` / `chat.stopStream`.
8. Final Slack completion is guaranteed by a durable final-delivery outbox.
9. If runtime dies, worker restarts runtime and resumes with Amp continue while preserving thread affinity and prompt identity.

## API Contract

All write endpoints require caller-supplied idempotency keys (`spawn_id`, `message_id`, `execute_id`, `release_id`).

### `POST /agent/message`

Purpose: append one Amp-compatible input event to transcript.

`event` is persisted as canonical Amp JSON (or a semantically equivalent representation that rehydrates to the same JSON line before execution).

If incoming content includes inline binary payloads (`image`/`document` with base64),
ingress stores blobs in `attachments` and rewrites transcript storage to
`attachment_ref` blocks.

Ingress persists enough attachment metadata for deterministic replay (`attachment_id`,
`sha256`, `media_type`, optional `source_path`, and size) and never depends on
runtime-local file paths for durability.

Reference: https://ampcode.com/manual#cli-streaming-json

Request shape:

```json
{
  "thread_key": "slack:C123:1742912345.000100",
  "assignment_generation": 12,
  "message_id": "client-idempotency-key",
  "event": {
    "type": "user",
    "message": {
      "role": "user",
      "content": [{ "type": "text", "text": "Please analyze this" }]
    }
  },
  "metadata": {
    "platform": "slack",
    "team_id": "T123",
    "channel": "C123",
    "thread_ts": "1742912345.000100",
    "user_id": "U123",
    "slack_event_id": "Ev123ABC456"
  }
}
```

Inline multimodal example (must be supported):

```json
{
  "thread_key": "slack:C123:1742912345.000100",
  "assignment_generation": 12,
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
  }
}
```

Response shape:

```json
{ "ok": true, "message_id": "..." }
```

Idempotency: unique by `(thread_key, message_id)`.

Spawn gating: `/agent/message` is accepted only if `(thread_key, assignment_generation)` maps to an active runtime assignment from `/agent/spawn`; otherwise return `409`.

Validation policy: API performs minimal envelope checks only; deeper semantic/runtime validation happens during execution and is persisted as durable outcomes.

Canonical stored transcript shape for multimodal inputs:

```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      { "type": "text", "text": "what do you see?" },
      {
        "type": "attachment_ref",
        "attachment_id": "att_123",
        "media_type": "image/jpeg",
        "source_path": "file:///Users/alice/images/example.jpg"
      }
    ]
  }
}
```

### `POST /agent/execute`

Purpose: enqueue one durable execution request for a thread.

Request shape:

```json
{
  "thread_key": "slack:C123:1742912345.000100",
  "assignment_generation": 12,
  "execute_id": "client-idempotency-key",
  "delivery": {
    "platform": "slack",
    "team_id": "T123",
    "channel": "C123",
    "thread_ts": "1742912345.000100",
    "recipient_user_id": "U123",
    "recipient_team_id": "T123"
  },
  "harness": "amp"
}
```

Response shape:

```json
{
  "ok": true,
  "execution_id": "exe_...",
  "execute_id": "client-idempotency-key",
  "assignment_generation": 12,
  "status": "queued"
}
```

Idempotency: unique by `(thread_key, execute_id)`.

Spawn gating: `/agent/execute` is accepted only if `(thread_key, assignment_generation)` maps to an active runtime assignment from `/agent/spawn`; otherwise return `409`.

`execution_id` is the canonical durable identifier returned by the system.

Validation policy: API validates only request envelope and delivery shape needed for downstream Slack calls, then persists and returns.

`recipient_user_id` and `recipient_team_id` are required when delivery target is a channel thread; for DM threads they can be omitted.

Execution request mental model:

1. One `/agent/execute` call means: run the current durable transcript once for this thread.
2. `execution_id` is that run's durable identity.
3. Retries/crashes create new attempts under the same `execution_id` until terminal state.
4. Slack final-delivery dedupe keys are based on `execution_id`, so each run gets one final answer.
5. `assignment_generation` ties message/execute calls to the exact spawn binding and prevents stale callers from writing to superseded assignments.

Identifier semantics:

1. `execute_id` is caller-provided idempotency identity.
2. `execution_id` is server-provided durable execution identity.
3. Status/cancel/read operations are keyed by `execution_id`.
4. `turn_id`/`turn_command` are not public API concepts in this redesign.

### `POST /agent/spawn`

Purpose: assign a warm runtime to a specific Slack thread and enforce affinity.

This is a SlackBot-facing control endpoint for assignment and prewarm. It is not a substitute for `/agent/execute`.

Access control: require privileged scope (for example `agent:spawn`) and restrict callers to trusted service identities (SlackBot/scheduler), not end users.

Request shape:

```json
{
  "thread_key": "slack:C123:1742912345.000100",
  "spawn_id": "client-idempotency-key",
  "harness": "amp",
  "persona_id": "prs_policy_default",
  "agents_md_override": null,
  "delivery": {
    "platform": "slack",
    "team_id": "T123",
    "channel": "C123",
    "thread_ts": "1742912345.000100"
  }
}
```

Response shape:

```json
{
  "ok": true,
  "runtime_id": "rtm_...",
  "thread_key": "slack:C123:1742912345.000100",
  "assignment_state": "assigned_idle",
  "assignment_generation": 12,
  "persona_id": "prs_policy_default",
  "prompt_ref": "persona:policy_default@v4",
  "effective_agents_md_sha256": "d88f..."
}
```

Idempotency: unique by `(thread_key, spawn_id)`.

Semantics:

1. Resolve requested prompt identity first.
2. If thread already has an active runtime assignment and prompt identity matches, return it.
3. If thread already has an active runtime assignment and prompt identity differs, reject spawn and require explicit release then respawn.
4. Else claim one unassigned warm runtime (or create one) and bind it to this thread.
5. An assigned runtime cannot be rebound to another thread while alive.
6. Rebinding requires terminating the runtime first and creating a new assignment.

Prompt semantics:

1. `persona_id` resolves through a DB-backed persona registry to a versioned system prompt artifact.
2. `prompt_ref` is an internal escape hatch for trusted callers only and must reference an immutable prompt artifact.
3. Prompt source precedence is: `agents_md_override` then `persona_id` registry lookup then internal `prompt_ref` then default prompt.
4. Effective prompt identity (`persona_id`, `prompt_ref`, `effective_agents_md_sha256`) is persisted with assignment generation.
5. Runtime restarts for the same assignment generation must reuse the same effective prompt identity.
6. Changing persona or override requires a new assignment generation (fresh spawn).
7. Unknown, disabled, or unauthorized `persona_id` causes spawn rejection before runtime assignment.
8. `agents_md_override` must enforce a strict size limit and UTF-8 validation at ingress.

### `POST /agent/threads/{thread_key}/release`

Purpose: explicitly release a thread assignment and avoid waiting for 24h idle sweeper.

Semantics:

1. Idempotent by `(thread_key, release_id)`.
2. Transitions active assignment generation to `released`.
3. If `cancel_non_terminal_executions=true`, queued/running executions for that generation are terminalized as `cancelled`.
4. If `cancel_non_terminal_executions=false`, queued/running executions for that generation may continue, but no new writes for that generation are accepted.
5. `stop_runtime=true` is valid only when no non-terminal executions remain for that generation.
6. `stop_runtime=true` with non-terminal executions and `cancel_non_terminal_executions=false` is rejected as invalid release flags.
7. After release, message/execute for that generation deterministically fail with stale-generation errors.
8. If non-terminal execution requests are allowed to continue, they run against their persisted `(thread_key, assignment_generation)` snapshot.

## API Statelessness And Minimal Validation

The API layer is intentionally thin so zero-downtime deploys are easy and safe.

1. API keeps no in-memory session state, runtime process handles, stream cursors, or sticky routing metadata.
2. API performs minimal ingress validation only: required fields present, JSON parses, payload size bounds, UTF-8 checks, and idempotency key shape checks.
3. API does not run orchestration logic in memory (no runtime affinity decisions, no retry orchestration, no execution ordering).
4. API persists intents/events in one transaction and returns quickly; workers perform all long-running orchestration.
5. Concurrency safety, replay safety, and exactly-once semantics are enforced by Postgres transactions, unique constraints, and row-lock state machines.
6. Semantic/runtime failures are recorded durably as execution attempt outcomes and projected to Slack; API servers remain stateless routers.
7. Rolling API deploys can run old/new versions concurrently without draining live executions because execution truth is durable in Postgres.
8. Spawn gating checks (`thread_key` + `assignment_generation`) are enforced by durable DB procedures/triggers, not in-memory API state.
9. Idempotency checks run before spawn-gating checks; same-key same-hash retries return existing rows, same-key different-hash writes fail.

## Mandatory Amp JSON Wire Contract

This is non-negotiable for runtime I/O.

1. Worker writes only Amp JSON envelopes to runtime stdin (NDJSON, one JSON object per line).
2. Worker must not invent non-Amp runtime envelope types like `turn.start` or `turn.done`.
3. Stdin lines are durably snapshot and replayable as exact JSON payloads.
4. Stdout lines are persisted raw before any normalization or Slack rendering.
5. Thinking output must survive persistence, replay, and downstream projection.
6. Ingest must accept Amp-compatible `text`, `image`, and `document` shapes with `source_path` and inline `source`.
7. Execution must resolve multimodal payloads from `attachments` refs, not from inline transcript base64.
8. The Amp runtime adapter may materialize resolved attachments into local files before writing stdin, but this materialization is derived only from durable attachment rows.

Amp stdin line shape:

```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [{ "type": "text", "text": "Please analyze this" }]
  }
}
```

Amp stdout event examples that must be persisted:

```json
{ "type": "stream_event", "event": { "type": "content_block_delta", "delta": { "type": "thinking_delta", "thinking": "..." } } }
```

```json
{
  "type": "assistant",
  "message": {
    "role": "assistant",
    "content": [
      { "type": "thinking", "thinking": "..." },
      { "type": "text", "text": "Final answer" }
    ],
    "stop_reason": "end_turn"
  }
}
```

Execution completion is a durable state transition (`running -> completed`), not a custom runtime wire event.

## Amp CLI Compatibility Notes (Local Repros)

Validated locally against Amp CLI `0.0.1774471707-g40b89f`:

1. Text-only NDJSON input works with `--stream-json --stream-json-input --stream-json-thinking`.
2. Thinking blocks are emitted as assistant content blocks and must be preserved end-to-end.
3. `amp threads continue` is the reliable continuation path after process/container restart.
4. Inline `image`/`document` JSON blocks are not consistently executable on this version, so runtime adapter must materialize from durable attachments into Amp-compatible local references.
5. Design keeps ingress Amp-compatible while execution remains deterministic through attachment-table-backed materialization.

Repro bundle for Amp team sharing: https://gist.github.com/gakonst/266935dd417eb4366ecc9d8838192ae5

## Attachments And Inline Blocks

Inline multimodal support and durable binary storage are both first-class.

1. Ingest accepts inline Amp blocks exactly.
2. Binary payloads are always extracted into `attachments` at ingress.
3. Transcript stores only `attachment_ref` entries for non-text payloads.
4. Execution processing always pulls attachment bytes from `attachments` by `attachment_id`.
5. Runtime input is materialized from pulled attachments into runtime-compatible form.
6. Rehydration/materialization preserves media metadata and `source_path` when available.
7. Missing or unreadable attachment rows cause deterministic execution failure/retry behavior; no silent drop.

### Attachment Resolution Pipeline

1. `/agent/message` validates each content block and accepts inline Amp multimodal shapes.
2. For each binary/multimodal block, ingress persists bytes and metadata into `attachments` and records immutable `attachment_id` + checksum.
3. Ingress rewrites transcript content to `attachment_ref` blocks only for non-text payloads.
4. `/agent/execute` reads only transcript events and `attachment_ref` metadata from durability storage.
5. Worker resolves each `attachment_ref` by loading bytes from `attachments` (not from client payloads and not from previous runtime files).
6. Worker materializes resolved attachments into per-attempt workspace files when required by the Amp adapter.
7. Worker snapshots execution materialization metadata (attachment ids/checksums/paths) with the attempt for deterministic retry.
8. Retry/replay re-runs the same resolution path from durable attachments and verifies checksums before execution.

## Control Plane Components

These are logical components and can be co-located initially:

1. SlackBot Adapter: primary Slack ingress/egress boundary.
2. Ingress API: performs minimal envelope validation for `/agent/message` and `/agent/execute`, then writes durable events.
3. Spawn Assigner: handles `/agent/spawn` and thread-pinned warm-runtime assignment.
4. Execution Worker: claims queued execution requests, ensures runtime, executes Amp, persists raw output.
5. Event Projector: maps raw runtime events into Slack render events and final artifacts.
6. Slack Delivery Worker: sends Slack stream updates and final completion with retry/dedupe.
7. Runtime Sweeper: enforces 24h idle shutdown.

No direct client-to-container stream is part of correctness.

## Warm Worker Thread Affinity (Critical)

Warm runtime assignment is strict and durable.

1. A runtime is either `unassigned` or assigned to exactly one `thread_key`.
2. Assignment transition `unassigned -> assigned(thread_key)` is atomic in the durability store.
3. While runtime is alive, `assigned_thread_key` is immutable.
4. `/agent/execute` can only write to a runtime whose `assigned_thread_key` equals request `thread_key`.
5. Any assignment mismatch is a hard safety error: reject the execution attempt and quarantine the runtime.
6. A runtime assigned to thread A cannot be reused for thread B; reuse requires runtime termination then fresh spawn.
7. Concurrent `/agent/spawn` calls are serialized with row-level locking so two threads cannot claim the same warm runtime.

### Spawn Claim Transaction

1. Lock thread assignment row for `thread_key`.
2. Resolve requested prompt identity before assignment decision.
3. If active assignment exists with matching prompt identity, return current `runtime_id` and `assignment_generation`.
4. If active assignment exists with different prompt identity, reject with prompt-mismatch conflict.
5. Else select one `unassigned` warm runtime using `FOR UPDATE SKIP LOCKED`.
6. If none available, create runtime and insert as assigned.
7. Persist assignment event with incremented `assignment_generation`.
8. Commit and return assignment payload.

`assignment_generation` is included in worker writes to prevent stale processes from writing to superseded assignments.

## Persona And AGENTS.md Contract

Prompt control is first-class and deterministic.

1. Runtime bootstrap must write the resolved effective prompt into workspace `AGENTS.md` before Amp starts.
2. Prompt resolution sources are ordered: inline `agents_md_override` then `persona_id` registry lookup then internal explicit `prompt_ref` then default base prompt.
3. The system persists prompt provenance (`persona_id`, `prompt_ref`) and fingerprint (`effective_agents_md_sha256`).
4. Execution processing validates assignment generation and prompt fingerprint before sending stdin.
5. If runtime prompt fingerprint does not match assignment, mark runtime unsafe, stop it, and respawn with correct prompt.
6. Amp continue on restart must preserve both `amp_thread_id` and effective prompt identity.
7. Prompt changes are explicit lifecycle events via new spawn generation, not in-place mutation.
8. If `agents_md_override` is persisted for restart durability, store it encrypted at rest and never log raw content.

Persona registry requirements:

1. Persona records are durable in Postgres with stable `persona_id` and versioned prompt references.
2. Registry supports active/disabled state and optional allowlist scoping by caller/workspace.
3. Spawn resolution must be deterministic against the committed persona row at assignment time.

## SlackBot Integration Contract (Primary)

SlackBot remains thin and reliable.

1. Verify Slack signatures, parse event envelope, and dedupe on `event_id`.
2. Acknowledge Events API requests with HTTP 2xx within 3 seconds, then process async.
3. Call `/agent/spawn` first so warm runtime is pinned to the Slack thread before execution.
4. Convert each user message to deterministic `/agent/message` writes.
5. Convert each trigger to deterministic `/agent/execute` writes.
6. Drive streaming UX from durable event log, not container sockets.
7. Final response correctness comes from durable final-delivery records.

Deterministic idempotency keys from Slack event:

1. `spawn_id = slack:{team_id}:{event_id}:spawn`
2. `message_id = slack:{team_id}:{event_id}:message`
3. `execute_id = slack:{team_id}:{event_id}:execute`
4. `assignment_generation` must be copied from spawn response into subsequent message/execute calls.
5. `release_id = slack:{team_id}:{event_id}:release` when explicit release is triggered.

Retry headers like `x-slack-retry-num` and `x-slack-retry-reason` are informational; dedupe remains keyed by `event_id`.

## Internal Stream Surface For SlackBot

The internal stream for SlackBot is a durable event cursor over projected runtime events.

1. Default transport is SSE because the workload is unidirectional and resume-friendly.
2. Streamable HTTP is optional but not required.
3. Stream reads from durable event log (`from_seq` or `Last-Event-ID`), never direct container attach.
4. `from_seq` is inclusive; `Last-Event-ID` takes precedence and resumes from `Last-Event-ID + 1`.
5. Stream is for UX only; execution correctness does not depend on stream liveness.

Event envelope:

```json
{
  "seq": 1287,
  "thread_key": "slack:C123:1742912345.000100",
  "execution_id": "exe_abc",
  "attempt_id": "att_2",
  "kind": "amp_raw_event",
  "payload": {
    "type": "assistant",
    "message": { "role": "assistant", "content": [{ "type": "text", "text": "..." }] }
  },
  "created_at": "2026-03-25T18:04:00Z"
}
```

Reconnect semantics:

1. SlackBot persists `last_seen_seq` per execution stream.
2. On restart/disconnect, SlackBot reconnects with `from_seq = last_seen_seq + 1`.
3. Server replays persisted events and tails live events.
4. If runtime restarts, stream continues with higher `attempt_id` and monotonic `seq`.
5. Terminal completion comes from durable execution state, not connection closure.

## Slack Native Streaming Delivery (Latest Docs)

User-visible streaming should use official Slack chat streaming APIs:

1. `chat.startStream` to open a stream reply in the user thread.
2. `chat.appendStream` to push progressive updates.
3. `chat.stopStream` to finalize.

Contract details from current Slack docs:

1. `chat.startStream` requires `channel` and `thread_ts`; for channels it also requires `recipient_user_id` and `recipient_team_id`.
2. `chat.appendStream` requires `channel`, `ts`, and `markdown_text`.
3. `chat.stopStream` requires `channel` and `ts`, and may include final `markdown_text`, `chunks`, `blocks`, and `metadata`.
4. `chunks` should be used for `markdown_text`, `task_update`, and `plan_update`.
5. Rate limits differ by method tier; delivery worker must honor `Retry-After` on 429s.

Progressive UX mapping:

1. Assistant text deltas project into `markdown_text` chunks.
2. Tool lifecycle/status updates project into `task_update` chunks.
3. Plan/agenda updates project into `plan_update` chunks.
4. Final rich response and metadata are attached on `chat.stopStream`.

Append coalescing policy:

1. Buffer tiny deltas and flush at fixed cadence to avoid request spam.
2. Respect Slack field size limits (for example 12k markdown fields).
3. Use adaptive backpressure when approaching rate limits.

## Runtime Container Contract (Dumb Pipe)

Each runtime container is intentionally minimal:

1. Read Amp NDJSON stdin.
2. Run Amp CLI in stream-json mode (`--stream-json --stream-json-input --stream-json-thinking`).
3. Emit Amp NDJSON stdout.
4. Keep no authoritative lifecycle state.
5. Be disposable at any time; orchestrator handles retries, replay, and continue.
6. Load resolved prompt into workspace `AGENTS.md` before Amp starts (persona-aware bootstrap).

## Core State Machines

### Execution Request State

`queued -> claimed -> running -> completed`

Failure branches:

`running -> retry_wait -> queued`

`running -> failed_permanent`

Cancel branches:

`running -> cancel_requested -> cancelled`

`queued -> cancelled`

Rule: exactly one running execution request per `thread_key`.

### Runtime State

`stopped -> starting -> ready -> busy -> idle -> stopped`

Failure branch:

`busy -> lost -> starting` (recover via Amp continue)

### Runtime Assignment State

`unassigned -> assigned(thread_key) -> assigned(thread_key) -> stopped`

Forbidden transition:

`assigned(thread_A) -> assigned(thread_B)`

Cross-thread reassignment is never allowed in-place.

### Slack Stream State

`not_started -> starting -> streaming -> stopping -> finalized`

Degraded branch:

`starting|streaming|stopping -> degraded -> finalized`

`degraded` means progressive streaming failed, but final response still must be delivered.

### Final Delivery State

`pending -> sending -> delivered`

Failure branch:

`sending -> retry_wait -> pending`

Terminal failure:

`sending -> dead_letter`

## Durable Management (Postgres-First)

In production, Postgres stores control-plane truth:

1. Transcript events and metadata.
2. Attachment refs and blob metadata.
3. Execution requests, attempts, and lifecycle transitions.
4. Runtime lease and liveness.
5. Runtime assignment state (`assigned_thread_key`, `assignment_generation`, `spawn_id`, `persona_id`, `prompt_ref`, `effective_agents_md_sha256`, `amp_thread_id`).
6. Raw Amp stdin snapshots for each attempt.
7. Raw Amp stdout events including thinking deltas/blocks.
8. Slack stream session state (`stream_message_ts`, `last_emitted_seq`, status).
9. Final delivery outbox and attempt history.

In-memory state is cache only.

## Storage Portability

Behavior must not depend on Postgres-specific logic.

1. Define a `DurabilityStore` interface for transcript, execution requests, runtime leases, runtime assignments, streams, and outbox.
2. Postgres adapter is production backend.
3. In-memory adapter is allowed for dev/degraded mode.
4. API and Amp protocol behavior stay identical across adapters.
5. Without Postgres, durability guarantees degrade but control flow remains the same.

## Amp Thread Continue Strategy

1. Persist `amp_thread_id` on the active assignment generation as soon as Amp exposes it.
2. Runtime startup checks for existing `amp_thread_id`.
3. If present, launch Amp in continue mode.
4. On runtime loss mid-execution, retry same execution attempt on a fresh container with continue.
5. If continue fails, replay transcript into a fresh Amp thread and persist new `amp_thread_id`.

This removes dependence on container-local memory.

## Slack Delivery Correctness

Two lanes, different guarantees:

1. Streaming lane is best-effort UX (`startStream`/`appendStream`).
2. Final lane is correctness-critical and durable.

Final lane guarantees:

1. `/agent/execute` transaction creates final-delivery obligation row in `awaiting_terminal` state.
2. Execution terminalization transaction updates the same row to sendable final payload (`pending`).
3. Final delivery key is deterministic (`thread_key + execution_id + final`) and unique.
4. Exactly one terminal final delivery record exists per execution request.
5. Retries use exponential backoff and respect `Retry-After`.
6. Reconciler backfills/repairs missing final-delivery obligations and marks unrecoverable rows `dead_letter` with operator-visible reason.
7. Final delivery includes deterministic token metadata (`final_key`, `execution_id`, `delivery_token`) for unknown-outcome reconciliation.

Execution watchdog guarantees:

1. Worker updates `last_progress_at` on durable stdin snapshot writes and durable stdout persistence.
2. A watchdog enforces both `silence_deadline` (no progress) and `hard_deadline` (max runtime).
3. When either deadline breaches, execution is forced to deterministic terminal state and final delivery obligation is promoted to `pending` with fallback summary.
4. Watchdog outcomes are explicit runtime events and are queryable by operators.

Recovery for Slack stream errors:

1. If `chat.appendStream` or `chat.stopStream` returns `message_not_in_streaming_state`, switch stream status to `degraded`.
2. If stream message `ts` exists, finalize with `chat.update` on that message.
3. If no stream message exists, deliver final via `chat.postMessage` in thread.
4. Mark final delivery by deterministic final key to prevent duplicates.

Unknown-outcome final delivery handling:

1. If a Slack write times out after send attempt, mark attempt outcome as unknown.
2. Reconciler checks thread history for matching delivery token metadata.
3. Retry final delivery only when reconciliation finds no token match.

Guarantee: each terminal execution request gets one correct final Slack response or an observable dead-letter.

## Resource Policy

1. Idle timeout is 24h (`86400s`) keyed off runtime `last_active_at`.
2. `last_active_at` updates on any stdin write or stdout read.
3. Sweeper stops runtimes idle beyond threshold and releases leases.
4. Capacity limiter bounds active runtimes; excess execution requests remain queued durably.
5. Next execution request after idle shutdown starts a new container and continues via `amp_thread_id`.
6. Idle shutdown never reassigns a still-alive runtime to another thread; reassignment happens only by new spawn after stop.

## Strongest Version (Recommended)

The strongest version is a protocol-first, Slack-native streaming, durable orchestration model.

1. `/agent/spawn` pins one warm runtime to one Slack thread.
2. `/agent/message` persists canonical Amp input events.
3. `/agent/execute` persists deterministic execution requests and returns fast.
4. Worker reconstructs stdin from durable transcript and sends only Amp JSON NDJSON to the thread-pinned runtime.
5. Prompt/persona identity is pinned per assignment generation and materialized as runtime `AGENTS.md`.
6. Runtime is replaceable/disposable; Amp continue ties attempts together.
7. SlackBot streams UX from durable event cursors and sends final responses from durable outbox.
8. Postgres is production durability; adapter abstraction keeps the architecture backend-agnostic.

### Hard Invariants

1. Every accepted `/agent/execute` maps to one durable `execution_id`.
2. Each `execution_id` has one terminal state (`completed`, `failed_permanent`, or `cancelled`).
3. Runtime stdin payloads are Amp JSON only.
4. Raw Amp thinking deltas/blocks are never dropped.
5. Per-thread execution is strictly serialized.
6. Each accepted execution request has exactly one final-delivery obligation row from enqueue time onward.
7. Each terminal execution request has at most one final Slack delivery record.
8. Running execution rows cannot remain in `running` without progress past configured watchdog limits.
9. Reconciler failure on one row cannot abort processing of other rows in the same tick.
10. A runtime assigned to thread A can never execute thread B.
11. Runtime prompt fingerprint must match assigned `persona_id`/`prompt_ref` metadata.
12. Every non-text execution payload is sourced from `attachments` by `attachment_id`; no execution reads inline base64 from transcript.
13. `/agent/message` and `/agent/execute` are rejected unless they reference an active spawn assignment generation.

### Logical Data Entities

These are conceptual entities, not commitments to current table shapes.

1. Threads and routing metadata.
2. Transcript input events.
3. Attachments and refs.
4. Execution requests and idempotency keys.
5. Execution attempts and retry metadata.
6. Runtime sessions, leases, and thread-affinity assignments.
7. Raw runtime event log.
8. Stream session projection for Slack.
9. Final delivery outbox and delivery attempts.
10. Persona registry with versioned prompt artifacts and access policy.

### Execution Processing Algorithm

1. Ingress transaction checks idempotency (`thread_key + execute_id`) first, returns existing row on same request hash, rejects mismatched hash, and only then validates active `(thread_key, assignment_generation)` for new writes.
2. Worker claims queued execution request with per-thread mutual exclusion.
3. Worker loads assignment row for execution's `(thread_key, assignment_generation)` snapshot and verifies runtime affinity (`assigned_thread_key == thread_key`), even if assignment state was later marked `released`.
4. Worker reconstructs canonical transcript events and resolves all `attachment_ref` entries from `attachments`.
5. Worker materializes Amp adapter input (including any file-backed multimodal references) from resolved attachments.
6. Worker snapshots exact stdin payload and attachment materialization manifest for attempt replay.
7. Worker ensures assigned runtime is alive, verifies prompt fingerprint, and resumes with continue when `amp_thread_id` exists.
8. Worker persists every raw stdout line before projection.
9. On terminal detection, worker commits execution terminal state and final delivery outbox promotion atomically.
10. Watchdog deadlines are evaluated from durable timestamps, not in-memory timers.

### Spawn Assignment Algorithm

1. `/agent/spawn` acquires thread-level lock.
2. Resolve requested prompt identity from `agents_md_override`, otherwise `persona_id` registry, otherwise internal `prompt_ref`.
3. If thread already has active assignment with matching prompt identity, return existing `runtime_id` and `assignment_generation`.
4. If thread already has active assignment with different prompt identity, reject with prompt-mismatch conflict.
5. Otherwise claim one unassigned warm runtime with row lock or create new runtime.
6. Persist `assigned_thread_key`, `assignment_generation`, prompt metadata, and spawn idempotency metadata atomically.
7. Return assignment payload used by subsequent `/agent/execute` path.

### Slack Streaming And Finalization Algorithm

1. Slack projector consumes durable events by `seq` and emits normalized render chunks.
2. Delivery worker opens stream via `chat.startStream` when first chunk arrives.
3. Delivery worker appends coalesced chunks via `chat.appendStream`.
4. On terminal execution state, delivery worker finalizes via `chat.stopStream`.
5. If streaming path fails, worker degrades gracefully and still sends one final answer via update/post fallback.
6. Final success marks outbox delivered and persists Slack identifiers.

### Failure Semantics

1. API crash after write: idempotency key returns existing record.
2. Worker crash mid-execution: lease expiry and replay from persisted stdin snapshot.
3. Container crash mid-execution: runtime restart with Amp continue.
4. Concurrent spawn races: both callers converge on same assignment for a thread, no double-claim.
5. Cross-thread write attempt: hard-fail attempt and quarantine offending runtime.
6. SlackBot crash mid-stream: reconnect by `last_emitted_seq` and resume stream state.
7. Slack API outage/rate limit: retry with backoff and `Retry-After` handling.
8. Missing attachment row/checksum mismatch: fail deterministically with retry policy and operator-visible error; never drop multimodal blocks.
9. Message/execute with stale assignment generation: reject at ingress with deterministic `409` and no side effects.
10. Stream reconnect older than retained event range: return deterministic `410 STREAM_RANGE_GONE` and require cursor reset policy.
11. One poisoned reconciliation row: row is marked with error metadata and skipped; tick continues processing other rows.

## Core Workflow Review

This design is robust because it splits concerns cleanly:

1. `/agent/spawn` handles warm-runtime assignment and persona/prompt materialization.
2. `/agent/message` handles durable transcript writes.
3. `/agent/execute` handles durable execution intent.
4. Worker handles deterministic execution and recovery.
5. Slack delivery lane handles UX streaming and final correctness.

The core path is intentionally boring and observable:

1. Every Slack trigger maps to deterministic `spawn_id`, `message_id`, and `execute_id`.
2. Every API call returns quickly after durable write.
3. Every execution request advances through durable states to one terminal result.
4. Every terminal result maps to one final delivery record.
5. Closing a thread can deterministically release assignment via `/agent/threads/{thread_key}/release`.

## Workflows Enabled On Top

With this engine, higher-level workflows become composition over the same primitives:

1. Interactive Slack thread copilot: `spawn -> message -> execute` for each user turn.
2. Scheduled cron workflows: scheduler emits synthetic events and drives the same three calls on schedule.
3. Recurring daily summaries: one dedicated thread with pinned runtime/persona_id and periodic executes.
4. Watcher/monitor workflows: external triggers append events and execute follow-up turns in same thread.
5. Multi-persona operations: different threads use different persona_ids/prompt refs without cross-thread leakage.
6. Durable background pipelines: non-Slack producers can enqueue work through message/execute while reusing orchestration guarantees.

All of these reuse the same durability, retry, affinity, and prompt-identity guarantees.

## One-Shot Cutover

No phased rollout and no compatibility path.

1. Remove legacy session/connect/reconnect correctness paths in same change set.
2. Ship `/agent/spawn`, `/agent/message`, `/agent/execute`, and internal cursor stream for SlackBot.
3. Switch SlackBot fully to deterministic IDs, event dedupe, and native Slack stream APIs.
4. Accept breakage for old in-flight sessions during cutover.
5. Rollback is full-stack rollback.

## Testability-First Design (Core Goal)

Fast iteration requires isolated and integrated testing of every component.

### Architecture Rules For Testability

1. Depend on explicit interfaces (`DurabilityStore`, `RuntimeAdapter`, `SlackClient`, `DeliveryAdapter`).
2. Keep worker behavior deterministic from persisted state.
3. Make all state transitions and runtime events observable.
4. Validate reconnect and replay behavior from durable cursors.

### Pytest Integrated Component Tests

1. `/agent/spawn` idempotency and affinity assignment correctness.
2. `/agent/message` and `/agent/execute` idempotency and execution request creation.
3. Worker + runtime adapter executes real Amp NDJSON request with thinking enabled.
4. Worker crash recovery resumes and reaches terminal state.
5. Runtime crash recovery uses Amp continue.
6. Persona/prompt test: resolved `AGENTS.md` fingerprint is persisted and reused on runtime restart.
7. Cross-thread protection test: runtime assigned to thread A rejects thread B execute.
8. Slack stream adapter tests `startStream`/`appendStream`/`stopStream` payloads and retry behavior.
9. Persona registry tests: unknown/disabled/unauthorized `persona_id` fails at spawn.
10. `agents_md_override` validation tests for size limits and encoding errors.
11. Final-delivery exactly-once semantics under duplicate retries.
12. Inline multimodal ingress test: binary blocks are rewritten to `attachment_ref` and bytes persist in `attachments`.
13. Execution materialization test: worker resolves every `attachment_ref` from `attachments` and never uses transcript inline base64.
14. Missing/corrupt attachment test: deterministic failure path and retry semantics are enforced.
15. Spawn-gating test: `/agent/message` and `/agent/execute` fail before spawn with `409 NO_ACTIVE_ASSIGNMENT`.
16. Stale-generation test: `/agent/message` and `/agent/execute` fail with `409 ASSIGNMENT_GENERATION_STALE` after reassignment.
17. Idempotency mismatch test: duplicate key with different payload fails deterministically.
18. Release test: explicit release endpoint unpins assignment and optionally cancels non-terminal executions.
19. Stream-range test: reconnect with expired cursor returns deterministic `410 STREAM_RANGE_GONE`.

### Docker-Compose E2E Scripts

1. Script injects synthetic Slack events and validates async 2xx ack path.
2. Script verifies `/agent/spawn` binds one runtime to one thread and survives retries.
3. Script verifies persona override on spawn is reflected in runtime `AGENTS.md` before first execute.
4. Script verifies SlackBot event dedupe by repeated `event_id` deliveries.
5. Script validates progressive stream UX (task/plan/text chunks) and final completion.
6. Script kills API/worker/runtime/SlackBot during execution and verifies eventual single final response.
7. Script verifies 24h idle shutdown using test TTL override.
8. Script posts inline image/document payloads and verifies execution succeeds only through attachment-table-backed materialization.

### Failure-Injection Matrix (Must-Have)

1. API restart during running execution.
2. Worker restart during running execution.
3. Concurrent `/agent/spawn` races across same and different threads.
4. Prompt mismatch on recovered runtime (wrong `AGENTS.md` fingerprint).
5. Runtime/container crash before terminal event.
6. Slack stream invalidation (`message_not_in_streaming_state`).
7. Slack 429 and 5xx conditions with retry/backoff.
8. Stream disconnect/reconnect with no lost or duplicated projected events.
9. Synthetic 10-minute wire EOF churn while runtime remains alive (proxy timeout simulation).
10. Missing-schema deploy (for example missing `suspended` check state) must fail readiness and page operators.

### CI Gates

1. Integration `pytest` suite passes for orchestration/runtime changes.
2. Compose E2E smoke suite passes before deploy.
3. Protocol golden tests enforce Amp stdin/stdout compatibility including thinking blocks.
4. Slack delivery contract tests enforce native stream API payload correctness.
5. Attachment-resolution golden tests enforce transcript `attachment_ref` rewrites and deterministic execute-time materialization.

## Acceptance Criteria

1. SlackBot flow uses `/agent/spawn`, `/agent/message`, and `/agent/execute` with deterministic idempotency keys.
2. A runtime assigned to thread A never executes thread B.
3. `persona_id` provided at spawn resolves via persona registry and unknown/disabled IDs are rejected before assignment.
4. Spawned persona/prompt override is loaded into runtime `AGENTS.md` and preserved across restart/continue for the same assignment generation.
5. Runtime crash during execution recovers using Amp continue.
6. API/worker/SlackBot restarts do not lose final Slack response.
7. Duplicate Slack webhook events do not produce duplicate final replies.
8. Stream UX recovers from disconnect using durable cursor replay.
9. No runtime remains alive beyond 24h inactivity.
10. Golden tests prove Amp JSON stdin lines and thinking events survive persistence/replay unchanged.
11. Multimodal execution always resolves bytes from `attachments`; transcript inline binary payloads are never required at execution time.
12. `/agent/message` and `/agent/execute` are rejected unless a matching active spawn assignment generation exists.
13. `/agent/threads/{thread_key}/release` deterministically transitions assignment state and blocks further writes for released generation.
14. Stream reconnect outside retained event range returns deterministic `410 STREAM_RANGE_GONE`.

## Reference Docs

1. Amp CLI streaming JSON: https://ampcode.com/manual#cli-streaming-json
2. Slack Events API: https://docs.slack.dev/apis/events-api/
3. Slack `chat.startStream`: https://docs.slack.dev/reference/methods/chat.startStream/
4. Slack `chat.appendStream`: https://docs.slack.dev/reference/methods/chat.appendStream/
5. Slack `chat.stopStream`: https://docs.slack.dev/reference/methods/chat.stopStream/
6. Slack Web API rate limits: https://docs.slack.dev/apis/web-api/rate-limits
