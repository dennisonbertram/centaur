import { beforeEach, describe, expect, it, vi } from "vitest";

import { BoltSlackApp } from "../src/lib/slack/app";
import { classifySlackError, SlackApiCallError } from "../src/lib/slack/errors";
import type { StreamChunk } from "../src/lib/slack/types";

const slackApiCall = vi.hoisted(() => vi.fn());
const slackUsersInfo = vi.hoisted(() => vi.fn());

vi.mock("@slack/web-api", () => ({
  WebClient: class WebClient {
    apiCall = slackApiCall;

    auth = {
      test: vi.fn(async () => ({ ok: true, user_id: "UBOT" })),
    };

    users = {
      info: slackUsersInfo,
    };
  },
}));

vi.mock("@slack/bolt", () => ({
  App: class App {
    event = vi.fn();

    processEvent = vi.fn();
  },
  verifySlackRequest: vi.fn(),
}));

function createAdapter() {
  return new BoltSlackApp("xoxb-test", "signing-secret").getSlackAdapter() as unknown as {
    stream(
      threadId: string,
      stream: AsyncIterable<string | StreamChunk>,
      options?: { taskDisplayMode?: "timeline" | "plan" },
    ): Promise<{ id: string }>;
  };
}

function streamCallParams(method: string): Record<string, unknown>[] {
  return slackApiCall.mock.calls
    .filter(([calledMethod]) => calledMethod === method)
    .map(([, params]) => params as Record<string, unknown>);
}

describe("Slack stream payloads", () => {
  beforeEach(() => {
    slackApiCall.mockReset();
    slackUsersInfo.mockReset();
    slackApiCall.mockImplementation(async (method: string) => ({
      ok: true,
      ...(method === "chat.startStream" ? { ts: "1700000000.000100" } : {}),
    }));
    slackUsersInfo.mockResolvedValue({ ok: true, user: { name: "alice" } });
  });

  it("uses chunk-mode for markdown and structured updates", async () => {
    const adapter = createAdapter();

    await adapter.stream("slack:C123:1700000000.000001", (async function* () {
      yield { type: "markdown_text", text: "\u200b" } satisfies StreamChunk;
      yield { type: "plan_update", title: "Completed" } satisfies StreamChunk;
      yield { type: "markdown_text", text: "pong" } satisfies StreamChunk;
    })(), { taskDisplayMode: "plan" });

    const start = streamCallParams("chat.startStream")[0];
    const appends = streamCallParams("chat.appendStream");

    expect(start).toEqual(expect.objectContaining({
      chunks: [{ type: "markdown_text", text: "\u200b" }],
    }));
    expect(start).not.toHaveProperty("markdown_text");
    expect(appends[0]).toEqual(expect.objectContaining({
      chunks: [{ type: "plan_update", title: "Completed" }],
    }));
    expect(appends[0]).not.toHaveProperty("markdown_text");
    expect(appends[1]).toEqual(expect.objectContaining({
      chunks: [{ type: "markdown_text", text: "pong" }],
    }));
    expect(appends[1]).not.toHaveProperty("markdown_text");
  });

  it("splits into follow-up messages when approaching Slack's text limit", async () => {
    const adapter = createAdapter();

    // 90% of 40k = 36k. Use a chunk that fills most of the budget so the
    // next markdown_text chunk pushes it over.
    const bigText = "x".repeat(36_000);

    await adapter.stream("slack:C123:1700000000.000001", (async function* () {
      yield { type: "markdown_text", text: bigText } satisfies StreamChunk;
      yield { type: "markdown_text", text: "overflow A" } satisfies StreamChunk;
      yield { type: "plan_update", title: "Done" } satisfies StreamChunk;
      yield { type: "markdown_text", text: "overflow B" } satisfies StreamChunk;
    })());

    // Stream was stopped before limit was hit
    const stops = streamCallParams("chat.stopStream");
    expect(stops).toHaveLength(1);
    // No appends — bigText was in startStream, "overflow A" exceeded the limit
    const appends = streamCallParams("chat.appendStream");
    expect(appends).toHaveLength(0);

    // Overflow posted as follow-up messages
    const posts = streamCallParams("chat.postMessage");
    expect(posts.length).toBeGreaterThanOrEqual(1);
    const postedText = posts.map((p) => p.text).join(" ");
    expect(postedText).toContain("overflow A");
    expect(postedText).toContain("overflow B");
    // plan_update is streaming-only UI — skipped
    expect(postedText).not.toContain("Done");
  });

  it("preserves table and rich text block content when overflow is posted as follow-ups", async () => {
    slackApiCall.mockImplementation(async (method: string) => {
      if (method === "chat.startStream") return { ok: true, ts: "1700000000.000100" };
      if (method === "chat.appendStream") return { ok: false, error: "msg_too_long" };
      return { ok: true };
    });
    const adapter = createAdapter();

    await adapter.stream("slack:C123:1700000000.000001", (async function* () {
      yield { type: "markdown_text", text: "first" } satisfies StreamChunk;
      yield {
        type: "blocks",
        blocks: [
          {
            type: "table",
            rows: [
              [{ type: "raw_text", text: "Asset" }, { type: "raw_text", text: "Move" }],
              [{ type: "raw_text", text: "BTC" }, { type: "raw_text", text: "+5%" }],
            ],
          },
          {
            type: "rich_text",
            elements: [{ type: "rich_text_section", elements: [{ type: "text", text: "View in Amp" }] }],
          },
        ],
      } satisfies StreamChunk;
    })());

    const postedText = streamCallParams("chat.postMessage").map((p) => p.text).join(" ");
    expect(postedText).toContain("Asset");
    expect(postedText).toContain("BTC");
    expect(postedText).toContain("+5%");
    expect(postedText).toContain("View in Amp");
  });

  it("posts rejected overflow chunks as follow-up messages when Slack returns msg_too_long", async () => {
    slackApiCall.mockImplementation(async (method: string) => {
      if (method === "chat.startStream") return { ok: true, ts: "1700000000.000100" };
      if (method === "chat.appendStream") return { ok: false, error: "msg_too_long" };
      return { ok: true };
    });
    const adapter = createAdapter();

    await adapter.stream("slack:C123:1700000000.000001", (async function* () {
      yield { type: "markdown_text", text: "first" } satisfies StreamChunk;
      yield { type: "markdown_text", text: "rejected overflow" } satisfies StreamChunk;
      yield { type: "markdown_text", text: "remaining overflow" } satisfies StreamChunk;
    })());

    const stops = streamCallParams("chat.stopStream");
    expect(stops).toHaveLength(1);
    const posts = streamCallParams("chat.postMessage");
    expect(posts.length).toBeGreaterThanOrEqual(1);
    const postedText = posts.map((p) => p.text).join(" ");
    expect(postedText).toContain("rejected overflow");
    expect(postedText).toContain("remaining overflow");
  });

  it("can start directly with a structured chunk", async () => {
    const adapter = createAdapter();

    await adapter.stream("slack:C123:1700000000.000001", (async function* () {
      yield { type: "plan_update", title: "Working" } satisfies StreamChunk;
    })());

    const start = streamCallParams("chat.startStream")[0];
    const appends = streamCallParams("chat.appendStream");

    expect(start).toEqual(expect.objectContaining({
      chunks: [{ type: "plan_update", title: "Working" }],
    }));
    expect(start).not.toHaveProperty("markdown_text");
    expect(appends).toHaveLength(0);
  });

  it("falls back to raw mention IDs when users.info cannot resolve a user", async () => {
    slackUsersInfo.mockResolvedValueOnce({ ok: false, error: "user_not_found" });
    const adapter = new BoltSlackApp("xoxb-test", "signing-secret").getSlackAdapter() as any;

    const message = await adapter.toBotMessage(
      "slack:C123:1700000000.000001",
      {
        type: "app_mention",
        text: "hi <@U404>",
        user: "U123",
        ts: "1700000000.000001",
      },
    );

    expect(message.text).toContain("U404");
  });
});

describe("Slack error classification", () => {
  it.each([
    ["channel_not_found", "invalid_destination", false],
    ["not_in_channel", "invalid_destination", false],
    ["user_not_found", "invalid_destination", false],
    ["restricted_action", "restricted_destination", false],
    ["restricted_action_thread_locked", "restricted_destination", false],
    ["invalid_blocks", "invalid_payload", false],
    ["msg_too_long", "invalid_payload", false],
    ["rate_limited", "rate_limited", true],
    ["internal_error", "transient_slack_error", true],
  ])("classifies Slack code %s", (code, errorClass, retryable) => {
    const result = classifySlackError(new SlackApiCallError("chat.postMessage", code, {
      ok: false,
      error: code,
    }));

    expect(result).toMatchObject({
      code,
      errorClass,
      retryable,
    });
  });

  it("treats 409 idempotency conflicts as non-retryable duplicates", () => {
    const result = classifySlackError({
      message: "Request failed with status code 409",
      response: { status: 409 },
    });

    expect(result.errorClass).toBe("duplicate_or_conflict");
    expect(result.retryable).toBe(false);
  });

  it("falls back to message matching for observed Slack error strings", () => {
    const result = classifySlackError(new Error("An API error occurred: user_not_found"));

    expect(result.errorClass).toBe("invalid_destination");
    expect(result.retryable).toBe(false);
  });
});
