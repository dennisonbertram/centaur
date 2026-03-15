/**
 * Tests for ProgressTracker — Slack streaming progress via task_card + plan blocks.
 *
 * Run:  pnpm vitest run src/lib/bot/progress-tracker.test.ts
 *
 * These are the CanonicalEvent shapes (post-normalization) that the tracker
 * consumes — NOT the raw SSE payloads.  Each test simulates a realistic Amp
 * turn by feeding events in the order Amp actually emits them.
 */

import { describe, it, expect } from "vitest";

// ── Minimal type stubs (avoid workspace dep resolution issues in test) ──

type ContentBlock =
  | { type: "text"; text: string }
  | { type: "tool_use"; id: string; name: string; input: Record<string, unknown> }
  | { type: "tool_result"; tool_use_id: string; content: unknown; is_error: boolean };

type SubagentActivity = { description: string; toolName?: string };

type CanonicalEvent =
  | { type: "assistant"; message: { content: ContentBlock[] } }
  | { type: "tool"; content: Array<{ tool_use_id: string; content: unknown; is_error: boolean }> }
  | { type: "reasoning"; text: string }
  | { type: "command_execution"; command: string; aggregated_output: string; exit_code?: unknown; status?: unknown }
  | { type: "subagent"; status: string; subagent_id: string; name?: string; summary?: string; error?: string; activity?: string; activities?: SubagentActivity[] }
  | { type: "result"; text: string }
  | { type: "error"; error: string }
  | { type: "system"; subtype: string; session_id?: string }
  | { type: "usage"; usage: Record<string, unknown>; model?: string; authoritative?: boolean };

type StreamChunk =
  | { type: "task_update"; id: string; title: string; status: string }
  | { type: "plan_update"; title: string }
  | { type: "markdown_text"; text: string };

// ── Inline ProgressTracker (snapshot of the algorithm under test) ──────

const MAX_VISIBLE_STEPS = 5;

type HistoryEntry = { toolId: string; title: string; status: "pending" | "in_progress" | "complete" | "error" };
type ActiveTool = { name: string; input: Record<string, unknown> };

class ProgressTracker {
  lastAssistantText = "";
  resultText = "";
  agentThreadId = "";
  private activeTools = new Map<string, ActiveTool>();
  private stepHistory: HistoryEntry[] = [];
  private planTitle = "";

  *update(event: CanonicalEvent): Generator<StreamChunk> {
    switch (event.type) {
      case "assistant":
        yield* this.onAssistant(event);
        break;
      case "tool":
        yield* this.onToolResult(event as any);
        break;
      case "subagent":
        yield* this.onSubagent(event as any);
        break;
      case "command_execution":
        yield* this.onCommand(event as any);
        break;
      case "result":
        this.resultText = event.text;
        break;
      case "error":
        yield { type: "markdown_text", text: `Error: ${event.error || "Unknown error"}` };
        break;
      case "system":
        if (event.subtype === "init" && event.session_id) this.agentThreadId = event.session_id;
        break;
    }
  }

  *finalize(): Generator<StreamChunk> {
    for (let i = 0; i < this.stepHistory.length; i++) {
      if (this.stepHistory[i].status === "in_progress" || this.stepHistory[i].status === "pending") {
        this.stepHistory[i].status = "complete";
        yield* this.emitSlot(i);
      }
    }
    yield { type: "plan_update", title: "Completed" };
  }

  *addHandoff(goal: string): Generator<StreamChunk> {
    this.activeTools.clear();
    this.lastAssistantText = "";
    this.resultText = "";
    yield* this.addStep(`handoff-${Date.now()}`, `Handed off → ${goal}`, "complete");
  }

  private *onAssistant(event: { type: "assistant"; message: { content: ContentBlock[] } }): Generator<StreamChunk> {
    if (!event.message?.content) return;
    let textInThisEvent = "";
    for (const block of event.message.content) {
      if (block.type === "tool_use") {
        this.lastAssistantText = "";
        this.activeTools.set(block.id, { name: block.name, input: block.input });
        const title = block.name;
        yield* this.addStep(block.id, title, "in_progress");
        yield* this.emitPlanTitle(title);
      } else if (block.type === "text" && block.text) {
        textInThisEvent = block.text;
      }
    }
    if (textInThisEvent && this.activeTools.size === 0) {
      this.lastAssistantText = textInThisEvent;
    }
  }

  private *onToolResult(event: { content: Array<{ tool_use_id: string; content: unknown; is_error: boolean }> }): Generator<StreamChunk> {
    if (!event.content) return;
    for (const block of event.content) {
      const active = this.activeTools.get(block.tool_use_id);
      if (!active) continue;
      this.activeTools.delete(block.tool_use_id);
      const status: "complete" | "error" = block.is_error ? "error" : "complete";
      yield* this.updateStep(block.tool_use_id, active.name, status);
    }
  }

  private *onSubagent(event: { status: string; subagent_id: string; name?: string; activity?: string; activities?: SubagentActivity[] }): Generator<StreamChunk> {
    const label = event.name || "Subagent";
    if (event.status === "started") {
      yield* this.addStep(event.subagent_id, `Subagent: ${label}`, "in_progress");
      yield* this.emitPlanTitle(`Subagent: ${label}`);
    } else if (event.status === "working") {
      const activity = event.activity || event.activities?.[0]?.description || "";
      const title = activity ? `Subagent: ${label} — ${activity.slice(0, 60)}` : `Subagent: ${label}`;
      yield* this.updateStep(event.subagent_id, title, "in_progress");
    } else if (event.status === "completed" || event.status === "failed") {
      yield* this.updateStep(event.subagent_id, `Subagent: ${label}`, event.status === "completed" ? "complete" : "error");
    }
  }

  private *onCommand(event: { command: string; exit_code?: unknown }): Generator<StreamChunk> {
    const cmd = event.command.slice(0, 60);
    const id = `cmd-${simpleHash(event.command)}`;
    const isError = event.exit_code !== undefined && event.exit_code !== 0;
    const status: "complete" | "error" = isError ? "error" : "complete";
    yield* this.addStep(id, `${isError ? "Failed" : "Ran"} — ${cmd}`, status);
  }

  private *addStep(toolId: string, title: string, status: "pending" | "in_progress" | "complete" | "error"): Generator<StreamChunk> {
    this.stepHistory.push({ toolId, title, status });
    if (this.stepHistory.length > MAX_VISIBLE_STEPS) {
      yield* this.emitVisibleWindow();
    } else {
      yield* this.emitSlot(this.stepHistory.length - 1);
    }
  }

  private *updateStep(toolId: string, title: string, status: "pending" | "in_progress" | "complete" | "error"): Generator<StreamChunk> {
    const idx = findLastIndex(this.stepHistory, (e) => e.toolId === toolId);
    if (idx === -1) return;
    this.stepHistory[idx].title = title;
    this.stepHistory[idx].status = status;
    yield* this.emitSlot(idx);
  }

  private *emitSlot(historyIndex: number): Generator<StreamChunk> {
    const windowStart = Math.max(0, this.stepHistory.length - MAX_VISIBLE_STEPS);
    const slotIndex = historyIndex - windowStart;
    if (slotIndex < 0 || slotIndex >= MAX_VISIBLE_STEPS) return;
    const entry = this.stepHistory[historyIndex];
    yield { type: "task_update", id: `step-${slotIndex}`, title: entry.title, status: entry.status };
  }

  private *emitVisibleWindow(): Generator<StreamChunk> {
    const start = Math.max(0, this.stepHistory.length - MAX_VISIBLE_STEPS);
    for (let i = start; i < this.stepHistory.length; i++) {
      yield { type: "task_update", id: `step-${i - start}`, title: this.stepHistory[i].title, status: this.stepHistory[i].status };
    }
  }

  private *emitPlanTitle(activityTitle: string): Generator<StreamChunk> {
    const newTitle = activityTitle.slice(0, 80);
    if (newTitle !== this.planTitle) {
      this.planTitle = newTitle;
      yield { type: "plan_update", title: newTitle };
    }
  }
}

function simpleHash(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

function findLastIndex<T>(arr: T[], predicate: (item: T) => boolean): number {
  for (let i = arr.length - 1; i >= 0; i--) { if (predicate(arr[i])) return i; }
  return -1;
}

// ── Helpers ────────────────────────────────────────────────────────────

function finalMessage(t: ProgressTracker): string {
  return (t.resultText || t.lastAssistantText).trim();
}

function collect(gen: Generator<StreamChunk>): StreamChunk[] {
  return [...gen];
}

function taskUpdates(chunks: StreamChunk[]): StreamChunk[] {
  return chunks.filter((c) => c.type === "task_update");
}

// ═══════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════

describe("ProgressTracker", () => {
  // ── Simple text response ──────────────────────────────────────────

  describe("simple text response", () => {
    it("captures text-only assistant message as final", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "Here is your answer." }] } }));
      expect(t.lastAssistantText).toBe("Here is your answer.");
      expect(finalMessage(t)).toBe("Here is your answer.");
    });

    it("last text event wins", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "First part." }] } }));
      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "Second part." }] } }));
      expect(t.lastAssistantText).toBe("Second part.");
    });
  });

  // ── Preamble before tool call ─────────────────────────────────────

  describe("preamble before tool call", () => {
    it("clears preamble when tool_use starts (separate events)", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "Let me look at the chat history..." }] } }));
      expect(t.lastAssistantText).toBe("Let me look at the chat history...");

      collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: "t1", name: "read_thread", input: { threadID: "T-abc" } }] } }));
      expect(t.lastAssistantText).toBe("");
      expect(finalMessage(t)).toBe("");
    });

    it("clears preamble when tool_use starts (same event)", () => {
      const t = new ProgressTracker();
      collect(t.update({
        type: "assistant",
        message: {
          content: [
            { type: "text", text: "Let me search for that..." },
            { type: "tool_use", id: "t1", name: "finder", input: { query: "auth" } },
          ],
        },
      }));
      expect(t.lastAssistantText).toBe("");
      expect(finalMessage(t)).toBe("");
    });
  });

  // ── Full tool call cycle ──────────────────────────────────────────

  describe("full tool call cycle", () => {
    it("captures final text after tool completes", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "Let me check..." }] } }));
      collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: "t1", name: "Read", input: { path: "/src/auth.ts" } }] } }));
      collect(t.update({ type: "tool", content: [{ tool_use_id: "t1", content: "file content", is_error: false }] }));
      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "The auth module works like this..." }] } }));
      expect(finalMessage(t)).toBe("The auth module works like this...");
    });

    it("emits task_update for tool_use start and completion", () => {
      const t = new ProgressTracker();
      const startChunks = collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: "t1", name: "Read", input: { path: "/x" } }] } }));
      expect(startChunks.some((c) => c.type === "task_update" && (c as any).status === "in_progress")).toBe(true);

      const doneChunks = collect(t.update({ type: "tool", content: [{ tool_use_id: "t1", content: "ok", is_error: false }] }));
      expect(doneChunks.some((c) => c.type === "task_update" && (c as any).status === "complete")).toBe(true);
    });
  });

  // ── Subagent events ───────────────────────────────────────────────

  describe("subagent events", () => {
    it("produces task_update chunks without affecting lastAssistantText", () => {
      const t = new ProgressTracker();
      const chunks = collect(t.update({ type: "subagent", status: "started", subagent_id: "sa-1", name: "Research task" }));
      expect(chunks.some((c) => c.type === "task_update" && (c as any).status === "in_progress")).toBe(true);
      expect(t.lastAssistantText).toBe("");

      const chunks2 = collect(t.update({ type: "subagent", status: "completed", subagent_id: "sa-1", name: "Research task", summary: "Found 5 results" }));
      expect(chunks2.some((c) => c.type === "task_update" && (c as any).status === "complete")).toBe(true);
      expect(t.lastAssistantText).toBe("");
    });
  });

  // ── Command execution ─────────────────────────────────────────────

  describe("command execution", () => {
    it("success produces complete task_update", () => {
      const t = new ProgressTracker();
      const chunks = collect(t.update({ type: "command_execution", command: "echo hello", aggregated_output: "hello", exit_code: 0 }));
      expect(chunks.some((c) => c.type === "task_update" && (c as any).status === "complete")).toBe(true);
    });

    it("failure produces error task_update", () => {
      const t = new ProgressTracker();
      const chunks = collect(t.update({ type: "command_execution", command: "make build", aggregated_output: "error", exit_code: 1 }));
      expect(chunks.some((c) => c.type === "task_update" && (c as any).status === "error")).toBe(true);
    });
  });

  // ── Result event ──────────────────────────────────────────────────

  describe("result event", () => {
    it("takes priority over lastAssistantText", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "Intermediate text." }] } }));
      collect(t.update({ type: "result", text: "Final result from turn.done" }));
      expect(t.resultText).toBe("Final result from turn.done");
      expect(finalMessage(t)).toBe("Final result from turn.done");
    });
  });

  // ── Error events ──────────────────────────────────────────────────

  describe("error events", () => {
    it("produces markdown_text chunk", () => {
      const t = new ProgressTracker();
      const chunks = collect(t.update({ type: "error", error: "Sandbox OOM killed" }));
      expect(chunks.some((c) => c.type === "markdown_text" && (c as any).text.includes("Sandbox OOM"))).toBe(true);
    });
  });

  // ── Reasoning events ──────────────────────────────────────────────

  describe("reasoning events", () => {
    it("does not affect lastAssistantText", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "reasoning", text: "I need to think about this carefully..." }));
      expect(t.lastAssistantText).toBe("");
      expect(finalMessage(t)).toBe("");
    });
  });

  // ── System init ───────────────────────────────────────────────────

  describe("system init", () => {
    it("captures agent thread ID", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "system", subtype: "init", session_id: "T-abc123" }));
      expect(t.agentThreadId).toBe("T-abc123");
    });
  });

  // ── Finalize ──────────────────────────────────────────────────────

  describe("finalize", () => {
    it("completes all in-progress tasks and sets plan title", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: "t1", name: "Read", input: {} }] } }));
      const chunks = collect(t.finalize());
      expect(chunks.some((c) => c.type === "task_update" && (c as any).status === "complete")).toBe(true);
      expect(chunks.some((c) => c.type === "plan_update" && (c as any).title === "Completed")).toBe(true);
    });
  });

  // ── Handoff ───────────────────────────────────────────────────────

  describe("handoff", () => {
    it("clears state and emits completed task", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "I'll hand this off." }] } }));
      const chunks = collect(t.addHandoff("Continue research"));
      expect(chunks.some((c) => c.type === "task_update" && (c as any).status === "complete")).toBe(true);
      expect(t.lastAssistantText).toBe("");
      expect(t.resultText).toBe("");
    });
  });

  // ── Sliding window ───────────────────────────────────────────────

  describe("sliding window", () => {
    it("first 5 tools each get a unique slot", () => {
      const t = new ProgressTracker();
      const starts: StreamChunk[] = [];
      for (let i = 0; i < 5; i++) {
        starts.push(...collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: `t${i}`, name: "Bash", input: { cmd: `echo ${i}` } }] } })));
        collect(t.update({ type: "tool", content: [{ tool_use_id: `t${i}`, content: "ok", is_error: false }] }));
      }
      const ids = taskUpdates(starts).map((c) => (c as any).id);
      expect(ids).toEqual(["step-0", "step-1", "step-2", "step-3", "step-4"]);
    });

    it("6th tool shifts window — slots show tools 2-6", () => {
      const t = new ProgressTracker();
      for (let i = 0; i < 5; i++) {
        collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: `t${i}`, name: "Read", input: { path: `/file${i}` } }] } }));
        collect(t.update({ type: "tool", content: [{ tool_use_id: `t${i}`, content: "ok", is_error: false }] }));
      }
      const shiftChunks = collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: "t5", name: "Read", input: { path: "/file5" } }] } }));
      const tasks = taskUpdates(shiftChunks);
      expect(tasks.length).toBe(5);
      expect(tasks.find((c) => (c as any).id === "step-4")?.status).toBe("in_progress");
      expect(tasks.find((c) => (c as any).id === "step-0")?.status).toBe("complete");
    });

    it("all slot IDs stay within step-0 to step-4", () => {
      const t = new ProgressTracker();
      const allChunks: StreamChunk[] = [];
      for (let i = 0; i < 10; i++) {
        allChunks.push(...collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: `t${i}`, name: "Read", input: { path: `/f${i}` } }] } })));
        allChunks.push(...collect(t.update({ type: "tool", content: [{ tool_use_id: `t${i}`, content: "ok", is_error: false }] })));
      }
      const ids = new Set(taskUpdates(allChunks).map((c) => (c as any).id));
      expect(ids).toEqual(new Set(["step-0", "step-1", "step-2", "step-3", "step-4"]));
    });
  });

  // ── Stream death scenarios ────────────────────────────────────────

  describe("stream death", () => {
    it("dies after preamble + tool_use → empty", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "Let me look at the Slack thread..." }] } }));
      collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: "t1", name: "read_thread", input: {} }] } }));
      expect(finalMessage(t)).toBe("");
    });

    it("dies after tool completes but before assistant text → empty", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: "t1", name: "Read", input: { path: "/x" } }] } }));
      collect(t.update({ type: "tool", content: [{ tool_use_id: "t1", content: "data", is_error: false }] }));
      expect(finalMessage(t)).toBe("");
    });
  });

  // ── Tool error followed by final text ─────────────────────────────

  describe("tool errors", () => {
    it("tool error followed by final text works", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: "t1", name: "Bash", input: { cmd: "make" } }] } }));
      collect(t.update({ type: "tool", content: [{ tool_use_id: "t1", content: "exit code 1", is_error: true }] }));
      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "The build failed." }] } }));
      expect(finalMessage(t)).toBe("The build failed.");
    });
  });

  // ── Realistic full turn ───────────────────────────────────────────

  describe("realistic full turn", () => {
    it("reasoning → preamble → Read → edit_file → final text", () => {
      const t = new ProgressTracker();
      collect(t.update({ type: "reasoning", text: "The user wants me to fix the bug in auth.ts" }));
      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "I'll fix the authentication bug." }] } }));
      expect(t.lastAssistantText).toBe("I'll fix the authentication bug.");

      collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: "r1", name: "Read", input: { path: "/src/auth.ts" } }] } }));
      expect(t.lastAssistantText).toBe("");
      collect(t.update({ type: "tool", content: [{ tool_use_id: "r1", content: "export function login() {...}", is_error: false }] }));

      collect(t.update({ type: "assistant", message: { content: [{ type: "tool_use", id: "e1", name: "edit_file", input: { path: "/src/auth.ts", old_str: "old", new_str: "new" } }] } }));
      collect(t.update({ type: "tool", content: [{ tool_use_id: "e1", content: "ok", is_error: false }] }));

      collect(t.update({ type: "assistant", message: { content: [{ type: "text", text: "Fixed the auth bug by updating the token validation." }] } }));
      expect(finalMessage(t)).toBe("Fixed the auth bug by updating the token validation.");
    });
  });
});
