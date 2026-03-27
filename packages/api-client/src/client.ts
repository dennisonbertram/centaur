import { EventSourceParserStream, type EventSourceMessage } from "eventsource-parser/stream";
import axios, { type AxiosInstance } from "axios";

export type InputContentBlock =
  | { type: "text"; text: string }
  | {
      type: "image";
      source_path?: string;
      source: { type: "base64"; media_type: string; data: string };
    }
  | {
      type: "document";
      source_path?: string;
      source: { type: "base64"; media_type: string; data: string };
    };

export interface SpawnOptions {
  threadKey: string;
  spawnId?: string;
  harness?: string;
  engine?: string;
  personaId?: string;
  agentsMdOverride?: string;
}

export interface SpawnResult {
  ok: boolean;
  runtime_id: string;
  thread_key: string;
  assignment_state: string;
  assignment_generation: number;
  persona_id?: string | null;
  prompt_ref?: string | null;
  effective_agents_md_sha256?: string | null;
}

export interface MessageOptions {
  threadKey: string;
  assignmentGeneration: number;
  messageId?: string;
  role?: string;
  event?: Record<string, unknown>;
  parts?: InputContentBlock[];
  userId?: string;
  metadata?: Record<string, unknown>;
}

export interface ExecuteOptions {
  threadKey: string;
  assignmentGeneration: number;
  executeId?: string;
  harness?: string;
  platform?: string;
  userId?: string;
  metadata?: Record<string, unknown>;
  delivery?: Record<string, unknown>;
}

export interface ExecutionAccepted {
  ok: boolean;
  execution_id: string;
  execute_id: string;
  assignment_generation: number;
  status: string;
  final_key: string;
  delivery_token: string;
  idempotent?: boolean;
}

export interface StreamEvent {
  eventId: number;
  eventKind: string;
  data: Record<string, unknown>;
}

export class CentaurClient {
  readonly http: AxiosInstance;
  private log?: { info: Function; warn: Function; error: Function };

  constructor(opts: {
    apiUrl: string;
    apiKey: string;
    logger?: { info: Function; warn: Function; error: Function };
  }) {
    this.log = opts.logger;
    this.http = axios.create({
      baseURL: opts.apiUrl,
      headers: { Authorization: `Bearer ${opts.apiKey}` },
      timeout: 30_000,
    });
  }

  private get authHeader(): string {
    return (this.http.defaults.headers["Authorization"] ??
      this.http.defaults.headers.common?.["Authorization"]) as string;
  }

  async spawn(opts: SpawnOptions): Promise<SpawnResult> {
    const { data } = await this.http.post("/agent/spawn", {
      thread_key: opts.threadKey,
      spawn_id: opts.spawnId,
      harness: opts.harness,
      engine: opts.engine,
      persona_id: opts.personaId,
      agents_md_override: opts.agentsMdOverride,
    });
    return data as SpawnResult;
  }

  async message(opts: MessageOptions): Promise<{ ok: boolean; message_id: string; attachment_ids: string[] }> {
    const body: Record<string, unknown> = {
      thread_key: opts.threadKey,
      assignment_generation: opts.assignmentGeneration,
      message_id: opts.messageId,
      metadata: opts.metadata,
      user_id: opts.userId,
    };

    if (opts.event) {
      body.event = opts.event;
    } else {
      body.role = opts.role ?? "user";
      body.parts = opts.parts ?? [];
    }

    const { data } = await this.http.post("/agent/message", body);
    return data as { ok: boolean; message_id: string; attachment_ids: string[] };
  }

  async execute(opts: ExecuteOptions): Promise<ExecutionAccepted> {
    const { data } = await this.http.post("/agent/execute", {
      thread_key: opts.threadKey,
      assignment_generation: opts.assignmentGeneration,
      execute_id: opts.executeId,
      harness: opts.harness,
      platform: opts.platform,
      user_id: opts.userId,
      metadata: opts.metadata,
      delivery: opts.delivery,
    });
    return data as ExecutionAccepted;
  }

  async *streamEvents(opts: {
    threadKey: string;
    afterEventId?: number;
    executionId?: string;
    pollMs?: number;
    signal?: AbortSignal;
  }): AsyncGenerator<StreamEvent, void, undefined> {
    const params = new URLSearchParams();
    if (opts.afterEventId !== undefined) params.set("after_event_id", String(opts.afterEventId));
    if (opts.executionId) params.set("execution_id", opts.executionId);
    if (opts.pollMs !== undefined) params.set("poll_ms", String(opts.pollMs));

    const url = `${this.http.defaults.baseURL}/agent/threads/${encodeURIComponent(opts.threadKey)}/events?${params.toString()}`;
    const res = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: this.authHeader,
        "X-Trace-Id": opts.threadKey,
      },
      signal: opts.signal,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`/agent/threads/{thread}/events failed (${res.status}): ${text.slice(0, 300)}`);
    }
    if (!res.body) return;

    const stream = (res.body as ReadableStream<Uint8Array>)
      .pipeThrough(new TextDecoderStream() as unknown as TransformStream<Uint8Array, string>)
      .pipeThrough(new EventSourceParserStream());

    for await (const event of stream as unknown as AsyncIterable<EventSourceMessage>) {
      if (!event.data || event.data === "[DONE]") continue;
      let parsed: Record<string, unknown> = { type: "unknown", raw: event.data };
      try {
        parsed = JSON.parse(event.data) as Record<string, unknown>;
      } catch {
        // keep raw fallback
      }
      yield {
        eventId: Number(event.id || 0),
        eventKind: event.event || "message",
        data: parsed,
      };
    }
  }

  async getExecution(executionId: string) {
    const { data } = await this.http.get(`/agent/executions/${encodeURIComponent(executionId)}`);
    return data as Record<string, unknown>;
  }

  async listExecutions(threadKey: string, limit = 20) {
    const { data } = await this.http.get(
      `/agent/threads/${encodeURIComponent(threadKey)}/executions`,
      { params: { limit } },
    );
    return data as { thread_key: string; executions: Array<Record<string, unknown>> };
  }

  async cancelExecution(executionId: string) {
    const { data } = await this.http.post(`/agent/executions/${encodeURIComponent(executionId)}/cancel`);
    return data as Record<string, unknown>;
  }

  async releaseThread(threadKey: string, opts?: { releaseId?: string; cancelInflight?: boolean }) {
    const { data } = await this.http.post(
      `/agent/threads/${encodeURIComponent(threadKey)}/release`,
      {
        release_id: opts?.releaseId,
        cancel_inflight: opts?.cancelInflight ?? false,
      },
    );
    return data as Record<string, unknown>;
  }

  async claimFinalDeliveries(opts: { consumerId: string; limit?: number; leaseSeconds?: number; platform?: string }) {
    const { data } = await this.http.post("/agent/final-deliveries/claim", {
      consumer_id: opts.consumerId,
      limit: opts.limit ?? 1,
      lease_seconds: opts.leaseSeconds ?? 60,
      platform: opts.platform,
    });
    return data as { deliveries: Array<Record<string, unknown>> };
  }

  async markFinalDelivered(executionId: string, consumerId?: string) {
    const { data } = await this.http.post(
      `/agent/final-deliveries/${encodeURIComponent(executionId)}/delivered`,
      { consumer_id: consumerId },
    );
    return data as Record<string, unknown>;
  }

  async markFinalFailed(executionId: string, error: string, opts?: { consumerId?: string; retryAfterSeconds?: number }) {
    const { data } = await this.http.post(
      `/agent/final-deliveries/${encodeURIComponent(executionId)}/failed`,
      {
        consumer_id: opts?.consumerId,
        error,
        retry_after_seconds: opts?.retryAfterSeconds ?? 15,
      },
    );
    return data as Record<string, unknown>;
  }

  async getStatus(threadKey: string) {
    const { data } = await this.http.get("/agent/status", { params: { key: threadKey } });
    return data as Record<string, unknown>;
  }
}
