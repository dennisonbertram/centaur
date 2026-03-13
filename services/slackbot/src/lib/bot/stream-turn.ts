import type { Chat, StreamChunk } from "chat";
import type { SlackAdapter } from "@chat-adapter/slack";
import type { CanonicalEvent } from "@centaur/harness-events";
import { normalizeThreadKey, splitThreadKey } from "@centaur/harness-events";
import { log } from "@/lib/logger";
import { ApiError } from "./api-client";
import {
  executeSSE,
  extractRunOptions,
  fetchThreadHarness,
  pollForLastResult,
  type ContentBlock,
  type Harness,
} from "./harness";
import { ProgressTracker } from "./progress-tracker";

type Thread = Parameters<Parameters<Chat["onNewMention"]>[0]>[0];

const THREAD_VIEWER_URL = process.env.THREAD_VIEWER_URL || "";
const KEEPALIVE_MS = 60_000;

const LOW_VALUE_RE = [
  /^i('ve| have) (handed off|delegated)/i,
  /^(handing off|delegating)/i,
  /^continuing in/i,
];

function isLowValue(text: string): boolean {
  if (!text) return true;
  return LOW_VALUE_RE.some((p) => p.test(text.trim()));
}

function formatFinal(
  text: string,
  harness: string,
  tracker: ProgressTracker,
  startTime: number,
  includeViewerLink: boolean,
): string {
  const dur = (Date.now() - startTime) / 1000;
  const durStr = dur < 10 ? `${dur.toFixed(1)}s` : `${Math.round(dur)}s`;
  const hLabel = tracker.agentThreadId
    ? `[${harness}](https://ampcode.com/threads/${tracker.agentThreadId})`
    : harness;
  const meta = [process.env.APP_NAME || "Centaur", hLabel, durStr].filter(Boolean);
  const parts = [`_${meta.join(" · ")}_\n\n`, text];
  if (includeViewerLink && THREAD_VIEWER_URL) {
    parts.push(`\n\n[Thread Viewer](${THREAD_VIEWER_URL}/${encodeURIComponent("")})`);
  }
  return parts.join("");
}

function formatErrorForSlack(error: unknown, context: string): string {
  if (error instanceof ApiError) {
    if (error.retryable && error.status === null) {
      return `${context}: API is unreachable. The service may be restarting — try again in ~30s.`;
    }
    if (error.status && error.status >= 500) {
      return `${context}: API returned ${error.status}. Try again shortly.`;
    }
    return `${context}: ${error.message}`;
  }
  if (error instanceof Error) return `${context}: ${error.message}`;
  return `${context}: unknown error`;
}

async function resolveAttachments(
  attachments: Array<{ url?: string; name?: string; mimeType?: string; fetchData?: () => Promise<Buffer> }>,
): Promise<ContentBlock[]> {
  const blocks: ContentBlock[] = [];
  for (const att of attachments) {
    if (!att.fetchData || !att.mimeType) continue;
    try {
      const data = await att.fetchData();
      const b64 = data.toString("base64");
      const base = { source: { type: "base64" as const, media_type: att.mimeType, data: b64 } };
      blocks.push(
        att.mimeType.startsWith("image/")
          ? { type: "image", ...base, ...(att.name ? { name: att.name } : {}) } as ContentBlock
          : { type: "document", ...base, ...(att.name ? { name: att.name } : {}) } as ContentBlock,
      );
    } catch (err) {
      log.warn("attachment_fetch_failed", {
        name: att.name || "unknown",
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }
  return blocks;
}

// ── Core streaming generator ────────────────────────────────────────────────

async function* streamTurn(
  threadKey: string,
  message: string | ContentBlock[],
  harness: Harness,
  tracker: ProgressTracker,
  userId?: string,
): AsyncGenerator<StreamChunk> {
  if (THREAD_VIEWER_URL) {
    yield { type: "markdown_text", text: `[Thread Viewer](${THREAD_VIEWER_URL}/${encodeURIComponent(threadKey)})` };
  }
  yield { type: "task_update", id: "init", title: "Starting…", status: "in_progress" };

  const stream = executeSSE(threadKey, message, harness, { platform: "slack", userId });
  let keepaliveId = 0;

  try {
    while (true) {
      const nextP = stream.next();
      const winner = await Promise.race([
        nextP.then((r) => ({ kind: "event" as const, result: r })),
        new Promise<{ kind: "keepalive" }>((resolve) =>
          setTimeout(() => resolve({ kind: "keepalive" }), KEEPALIVE_MS),
        ),
      ]);

      let result: IteratorResult<CanonicalEvent, string>;
      if (winner.kind === "keepalive") {
        yield { type: "task_update", id: `keepalive-${keepaliveId++}`, title: "Working…", status: "in_progress" };
        result = await nextP;
      } else {
        result = winner.result;
      }

      if (result.done) break;

      if (tracker.update(result.value)) {
        for (const chunk of tracker.pendingChunks()) yield chunk;
      }
    }
  } catch (err) {
    log.warn("stream_error", {
      thread_key: threadKey,
      error: err instanceof Error ? err.message : String(err),
    });
  }

  if (!tracker.initCompleted) {
    yield { type: "task_update", id: "init", title: "Started", status: "complete" };
  }
}

// ── Public entry point ──────────────────────────────────────────────────────

export async function handleMessage(
  bot: Chat,
  thread: Thread,
  messageText: string,
  isFirstMessage: boolean,
  attachments: Array<{ url?: string; name?: string; mimeType?: string; fetchData?: () => Promise<Buffer> }>,
  userId?: string,
  slackTs?: string,
) {
  const rawThreadId = thread.id;
  const threadKey = normalizeThreadKey(rawThreadId);

  let activeHarness: Harness | null = null;
  if (!isFirstMessage) {
    try {
      activeHarness = await fetchThreadHarness(threadKey);
    } catch (error) {
      log.warn("thread_harness_recovery_failed", {
        thread: threadKey,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  const parsed = extractRunOptions(messageText);
  const harness: Harness = isFirstMessage ? parsed.harness : (activeHarness ?? parsed.harness);

  log.info("message_received", {
    thread_key: threadKey,
    harness,
    is_first_message: isFirstMessage,
    has_attachments: Boolean(attachments.length),
    user_id: userId,
  });

  if (!isFirstMessage && !activeHarness && !parsed.harnessExplicit) {
    await thread.post(
      "I could not recover the active harness for this thread. Please retry with an explicit harness flag (for example `--legal`).",
    );
    return;
  }
  if (!isFirstMessage && activeHarness && parsed.harnessExplicit && parsed.harness !== activeHarness) {
    await thread.post("This thread is already running with a different harness. Start a new thread to switch.");
    return;
  }
  if (!parsed.cleanedText) {
    await thread.post("Please provide a prompt after flags. Example: `--amp build me a dashboard`.");
    return;
  }

  const contentBlocks = await resolveAttachments(attachments);
  const message: string | ContentBlock[] = contentBlocks.length > 0
    ? [{ type: "text" as const, text: parsed.cleanedText }, ...contentBlocks]
    : parsed.cleanedText;

  const tracker = new ProgressTracker();
  const startTime = Date.now();
  log.info("execute_start", { thread_key: threadKey, harness });

  try {
    let sentMessage: Awaited<ReturnType<typeof thread.post>> | null = null;
    try {
      sentMessage = await thread.post(
        streamTurn(threadKey, message, harness, tracker, userId),
      );
    } catch (streamErr) {
      const errMsg = streamErr instanceof Error ? streamErr.message : String(streamErr);
      if (errMsg.includes("message_not_in_streaming_state")) {
        log.warn("slack_stream_expired", { thread_key: threadKey });
        const fallback = await pollForLastResult(threadKey);
        if (fallback && !isLowValue(fallback)) {
          await thread.post({ markdown: fallback });
        } else if (THREAD_VIEWER_URL) {
          await thread.post({ markdown: `Agent completed. [View full output](${THREAD_VIEWER_URL}/${encodeURIComponent(threadKey)})` });
        }
        return;
      }
      throw streamErr;
    }

    const finalText = (tracker.resultText || tracker.lastAssistantText).trim();
    const durationS = (Date.now() - startTime) / 1000;
    log.info("execute_complete", {
      thread_key: threadKey,
      harness,
      duration_s: Math.round(durationS * 10) / 10,
      result_length: finalText.length,
    });

    if (finalText && !isLowValue(finalText)) {
      try {
        const editParts = [formatFinal(finalText, harness, tracker, startTime, false)];
        if (THREAD_VIEWER_URL) {
          editParts.push(`\n\n[Thread Viewer](${THREAD_VIEWER_URL}/${encodeURIComponent(threadKey)})`);
        }
        await sentMessage.edit({ markdown: editParts.join("") });
      } catch {
        // best-effort — streamed message already has the final text
      }
    }

    if (finalText) {
      try {
        const slack = bot.getAdapter("slack") as SlackAdapter;
        const { channel, threadTs } = splitThreadKey(rawThreadId);
        await slack.setAssistantTitle(channel, threadTs, finalText.slice(0, 60));
      } catch {
        // best-effort — only works in assistant threads (DMs)
      }
    }
  } catch (error) {
    log.error("execute_error", { thread_key: threadKey, error: error instanceof Error ? error.message : String(error) });
    await thread.post(async function* () {
      yield { type: "task_update" as const, id: "init", title: "Failed", status: "error" as const };
      yield { type: "markdown_text" as const, text: formatErrorForSlack(error, "Agent request failed") };
    }());
  }
}
