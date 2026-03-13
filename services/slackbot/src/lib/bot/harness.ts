import { log } from "@/lib/logger";
import { resilientFetch, ApiError, API_URL } from "./api-client";
import type { CanonicalEvent } from "@centaur/harness-events";
import { sleep } from "@/lib/utils";

export type Harness = string;

export type ContentBlock =
  | { type: "text"; text: string }
  | { type: "image"; source: { type: "base64"; media_type: string; data: string } }
  | { type: "document"; source: { type: "base64"; media_type: string; data: string } };

type RunOptions = {
  harness: Harness;
  cleanedText: string;
  harnessExplicit: boolean;
};

export function extractRunOptions(text: string): RunOptions {
  let cleaned = text;
  let harness: Harness = "amp";
  let harnessExplicit = false;

  const kvMatch = cleaned.match(/\bharness\s*=\s*([A-Za-z0-9_-]+)\b/i);
  if (kvMatch) {
    harness = kvMatch[1].toLowerCase();
    harnessExplicit = true;
    cleaned = (
      cleaned.slice(0, kvMatch.index) + cleaned.slice(kvMatch.index! + kvMatch[0].length)
    ).trim();
  }

  const engineFlags: Array<{ regex: RegExp; value: string }> = [
    { regex: /(^|\s)--amp(?=\s|$)/gi, value: "amp" },
    { regex: /(^|\s)--claude(?=\s|$)/gi, value: "claude-code" },
    { regex: /(^|\s)--claude-code(?=\s|$)/gi, value: "claude-code" },
    { regex: /(^|\s)--codex(?=\s|$)/gi, value: "codex" },
    { regex: /(^|\s)--pi(?=\s|$)/gi, value: "pi-mono" },
    { regex: /(^|\s)--pi-mono(?=\s|$)/gi, value: "pi-mono" },
  ];
  for (const { regex, value } of engineFlags) {
    const matched = regex.test(cleaned);
    regex.lastIndex = 0;
    if (matched) {
      harness = value;
      harnessExplicit = true;
      cleaned = cleaned.replace(regex, " ");
      regex.lastIndex = 0;
    }
  }

  cleaned = cleaned.replace(/(^|\s)--(engine|model)\s+[A-Za-z0-9._-]+(?=\s|$)/gi, " ");
  cleaned = cleaned.replace(/(^|\s)--(opus|sonnet|haiku)(?=\s|$)/gi, " ");
  cleaned = cleaned.replace(/\bmodel\s*=\s*[A-Za-z0-9._-]+\b/gi, "");

  const knownFlags = new Set([
    "amp", "claude", "claude-code", "codex", "pi", "pi-mono",
    "opus", "sonnet", "haiku", "engine", "model",
  ]);
  const genericFlagRegex = /(^|\s)--([a-z][a-z0-9-]*)(?=\s|$)/gi;
  let genericMatch: RegExpExecArray | null;
  while ((genericMatch = genericFlagRegex.exec(cleaned)) !== null) {
    const flag = genericMatch[2];
    if (knownFlags.has(flag)) continue;
    harness = flag;
    harnessExplicit = true;
  }
  cleaned = cleaned.replace(genericFlagRegex, " ");

  cleaned = cleaned.replace(/\s+/g, " ").trim();
  return { harness, cleanedText: cleaned, harnessExplicit };
}

// ── SSE streaming ───────────────────────────────────────────────────────────
// All functions below expect pre-normalized thread keys (channel:thread_ts).

async function* readSSEStream(
  res: Response,
): AsyncGenerator<CanonicalEvent, string, undefined> {
  if (!res.body) return "";

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let lastAssistantText = "";
  let resultText = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    while (buf.includes("\n\n")) {
      const boundary = buf.indexOf("\n\n");
      const raw = buf.slice(0, boundary);
      buf = buf.slice(boundary + 2);

      const dataLines = raw
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trim());
      if (dataLines.length === 0) continue;
      const payload = dataLines.join("\n");
      if (payload === "[DONE]") return resultText || lastAssistantText;

      try {
        const ce = JSON.parse(payload) as CanonicalEvent;
        if (ce.type === "result" && "text" in ce) resultText = ce.text;
        else if (ce.type === "assistant" && ce.message?.content) {
          for (const block of ce.message.content) {
            if (block.type === "text" && block.text) lastAssistantText = block.text;
          }
        }
        yield ce;
      } catch {
        // skip unparseable
      }
    }
  }

  return resultText || lastAssistantText;
}

function isBusyRunError(message: string): boolean {
  const lower = message.toLowerCase();
  return lower.includes("already in progress") || lower.includes("run is already in progress");
}

export async function* executeSSE(
  threadKey: string,
  message: string | ContentBlock[],
  harness: Harness,
  options?: { platform?: string; userId?: string },
): AsyncGenerator<CanonicalEvent, string, undefined> {
  const maxBusyRetries = 4;

  for (let attempt = 1; attempt <= maxBusyRetries; attempt++) {
    log.info("sse_connect", { thread_key: threadKey, harness });

    const body: Record<string, unknown> = {
      thread_key: threadKey,
      message,
      harness,
    };
    if (options?.platform) body.platform = options.platform;
    if (options?.userId) body.user_id = options.userId;

    const res = await resilientFetch(`${API_URL}/agent/execute`, {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "X-Trace-Id": threadKey },
      timeoutMs: 10 * 60_000,
      maxAttempts: 1,
      stream: true,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      if (isBusyRunError(text) && attempt < maxBusyRetries) {
        await sleep(Math.min(300 * Math.pow(2, attempt - 1), 2500));
        continue;
      }
      throw new ApiError(
        `/agent/execute failed (${res.status}): ${text.slice(0, 300)}`,
        res.status,
        res.status >= 500,
      );
    }

    log.info("sse_streaming", { thread_key: threadKey });
    return yield* readSSEStream(res);
  }

  return "";
}

export async function fetchThreadHarness(threadKey: string): Promise<Harness | null> {
  try {
    const res = await resilientFetch(
      `${API_URL}/agent/status?key=${encodeURIComponent(threadKey)}`,
      { timeoutMs: 5_000, maxAttempts: 1 },
    );
    if (!res.ok) return null;
    const data = (await res.json()) as Record<string, unknown>;
    return (data.harness as string) || null;
  } catch {
    return null;
  }
}

export async function postContextMessage(
  threadKey: string,
  text: string,
  options?: {
    source?: string;
    userId?: string;
    messageId?: string;
    slackTs?: string;
    attachments?: Array<{ url: string; name: string; mimeType?: string }>;
  },
): Promise<void> {
  const metadata: Record<string, unknown> = {};
  if (options?.source) metadata.source = options.source;
  if (options?.userId) metadata.user_id = options.userId;
  if (options?.attachments?.length) metadata.attachments = options.attachments;
  if (options?.messageId) metadata.message_id = options.messageId;
  if (options?.slackTs) metadata.slack_ts = options.slackTs;

  const res = await resilientFetch(`${API_URL}/agent/messages`, {
    method: "POST",
    body: JSON.stringify({
      thread_key: threadKey,
      messages: [{ role: "user", parts: [{ type: "text", text }], user_id: options?.userId, metadata }],
    }),
    timeoutMs: 10_000,
  });
  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new ApiError(`/agent/messages failed (${res.status}): ${errText.slice(0, 300)}`, res.status, res.status >= 500);
  }
}

export async function pollForLastResult(threadKey: string, maxWaitMs = 5 * 60_000): Promise<string> {
  const deadline = Date.now() + maxWaitMs;
  while (Date.now() < deadline) {
    try {
      const res = await resilientFetch(
        `${API_URL}/agent/status?key=${encodeURIComponent(threadKey)}`,
        { timeoutMs: 10_000, maxAttempts: 1 },
      );
      if (res.ok) {
        const data = (await res.json()) as Record<string, unknown>;
        if (!data.busy) {
          const result = data.last_result;
          if (typeof result === "string" && result.trim()) return result.trim();
          return "";
        }
      }
    } catch {
      // keep polling
    }
    await new Promise((r) => setTimeout(r, 3_000));
  }
  return "";
}
