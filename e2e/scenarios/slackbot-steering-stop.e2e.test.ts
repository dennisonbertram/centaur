import { describe, expect, it } from "vitest";

import { createE2EContext } from "../src/harness/scenario";

describe("slackbot steering", () => {
  it("stops an in-flight long generation when a stop message is sent", async () => {
    const ctx = await createE2EContext();
    const slackbot = ctx.mockSlackbot();
    const nonce = `CENTAUR_STEER_${Date.now()}`;

    const started = await slackbot.startMention({
      text: [
        `Write 40 haiku about ephemeral Kubernetes clusters. Include ${nonce} in every haiku.`,
        "Number each haiku. Do not summarize; write all 40 haiku in full.",
      ].join(" "),
      timeoutMs: 300_000,
    });

    const stopped = await slackbot.sendStop(started, { timeoutMs: 180_000 });

    expect(["steered", "cancel_requested", "cancelled"]).toContain(stopped.steerStatus);
    expect(["cancelled", "completed"]).toContain(stopped.terminal.status);

    if (stopped.terminal.status === "completed") {
      expect(stopped.terminal.finalText).toMatch(/stop|stopped|cancel|cancelled|interrupt|interrupted/i);
    }

    // A non-stopped run would usually contain the nonce many times. Keep the
    // assertion intentionally loose because Amp may emit a short acknowledgement
    // after steering instead of a hard cancellation.
    const nonceCount = stopped.terminal.finalText.split(nonce).length - 1;
    expect(nonceCount).toBeLessThan(5);

    console.log(JSON.stringify(ctx.metrics.summary({
      scenario: "slackbot-steering-stop",
      threadKey: started.threadKey,
      runId: started.runId,
      executionId: started.executionId,
      steerStatus: stopped.steerStatus,
      terminalStatus: stopped.terminal.status,
      terminalReason: stopped.terminal.terminalReason,
      finalTextChars: stopped.terminal.finalText.length,
      eventCount: stopped.terminal.events.length,
    }), null, 2));
  });
});
