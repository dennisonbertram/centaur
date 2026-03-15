import type { CanonicalEvent } from "@centaur/harness-events";
import type { StreamChunk } from "chat";

/**
 * ProgressTracker — converts CanonicalEvents into Slack streaming chunks.
 *
 * Uses Slack's native AI streaming primitives:
 *   - `task_update`  → task_card blocks (individual agent steps)
 *   - `plan_update`  → plan block title (groups tasks under a heading)
 *   - `markdown_text` → streamed text content
 *
 * The plan block wraps task cards into a collapsible group. Each task card
 * has an id, title, status (pending/in_progress/complete/error), optional
 * details, and optional output.
 *
 * Task IDs use a fixed sliding window of MAX_VISIBLE_STEPS slots (step-0
 * through step-4). When a new task exceeds the window, the entire window
 * shifts up — old tasks scroll off the top, keeping the display compact.
 */

const MAX_VISIBLE_STEPS = 5;

type HistoryEntry = {
  toolId: string;
  title: string;
  status: "pending" | "in_progress" | "complete" | "error";
};

type ActiveTool = { name: string; input: Record<string, unknown> };

export class ProgressTracker {
  /** Last assistant text block (used as fallback final answer). */
  lastAssistantText = "";
  /** Explicit result from turn.done. Takes priority over lastAssistantText. */
  resultText = "";
  /** Agent thread ID (Amp session ID from system.init). */
  agentThreadId = "";

  private activeTools = new Map<string, ActiveTool>();
  private stepHistory: HistoryEntry[] = [];

  // ── Public API ───────────────────────────────────────────────────────────

  /** Process a canonical event and yield streaming chunks for Slack. */
  *update(event: CanonicalEvent): Generator<StreamChunk> {
    switch (event.type) {
      case "assistant":
        yield* this.onAssistant(event);
        break;
      case "tool":
        yield* this.onToolResult(event);
        break;
      case "subagent":
        yield* this.onSubagent(event);
        break;
      case "command_execution":
        yield* this.onCommand(event);
        break;
      case "result":
        this.resultText = event.text;
        break;
      case "error":
        yield { type: "markdown_text", text: `Error: ${event.error || "Unknown error"}` };
        break;
      case "system":
        if (event.subtype === "init" && event.session_id) {
          this.agentThreadId = event.session_id;
        }
        break;
      // reasoning, file_change, usage — no Slack output
    }
  }

  /** Finalize all in-progress tasks and set the plan title to "Completed". */
  *finalize(): Generator<StreamChunk> {
    for (let i = 0; i < this.stepHistory.length; i++) {
      if (this.stepHistory[i].status === "in_progress" || this.stepHistory[i].status === "pending") {
        this.stepHistory[i].status = "complete";
        yield* this.emitSlot(i);
      }
    }
    yield { type: "plan_update", title: "Completed" };
  }

  /** Record a handoff as a completed task. */
  *addHandoff(goal: string): Generator<StreamChunk> {
    this.activeTools.clear();
    this.lastAssistantText = "";
    this.resultText = "";
    yield* this.addStep(`handoff-${Date.now()}`, `Handed off → ${goal}`, "complete");
  }

  // ── Event handlers ─────────────────────────────────────────────────────

  private *onAssistant(event: Extract<CanonicalEvent, { type: "assistant" }>): Generator<StreamChunk> {
    if (!event.message?.content) return;
    let textInThisEvent = "";
    for (const block of event.message.content) {
      if (block.type === "tool_use") {
        this.lastAssistantText = "";
        this.activeTools.set(block.id, { name: block.name, input: block.input });
        const title = friendlyToolLabel(block.name, block.input);
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

  private *onToolResult(event: Extract<CanonicalEvent, { type: "tool" }>): Generator<StreamChunk> {
    if (!event.content) return;
    for (const block of event.content) {
      const active = this.activeTools.get(block.tool_use_id);
      if (!active) continue;
      this.activeTools.delete(block.tool_use_id);
      const status = block.is_error ? "error" : "complete";
      const title = friendlyToolLabel(active.name, active.input, !block.is_error);
      yield* this.updateStep(block.tool_use_id, title, status);
    }
  }

  private *onSubagent(event: Extract<CanonicalEvent, { type: "subagent" }>): Generator<StreamChunk> {
    const label = event.name || "Subagent";
    if (event.status === "started") {
      const title = `Subagent: ${label}`;
      yield* this.addStep(event.subagent_id, title, "in_progress");
      yield* this.emitPlanTitle(title);
    } else if (event.status === "working") {
      const activity = event.activity || event.activities?.[0]?.description || "";
      const title = activity ? `Subagent: ${label} — ${truncate(activity, 60)}` : `Subagent: ${label}`;
      yield* this.updateStep(event.subagent_id, title, "in_progress");
      yield* this.emitPlanTitle(title);
    } else if (event.status === "completed" || event.status === "failed") {
      const status = event.status === "completed" ? "complete" : "error";
      yield* this.updateStep(event.subagent_id, `Subagent: ${label}`, status);
    }
  }

  private *onCommand(event: Extract<CanonicalEvent, { type: "command_execution" }>): Generator<StreamChunk> {
    const cmd = truncate(event.command, 60);
    const id = `cmd-${simpleHash(event.command)}`;
    const isError = event.exit_code !== undefined && event.exit_code !== 0;
    const status = isError ? "error" : "complete";
    const title = `${isError ? "Failed" : "Ran"} — ${cmd}`;
    yield* this.addStep(id, title, status);
  }

  // ── Sliding window ─────────────────────────────────────────────────────

  private *addStep(
    toolId: string,
    title: string,
    status: "pending" | "in_progress" | "complete" | "error",
  ): Generator<StreamChunk> {
    this.stepHistory.push({ toolId, title, status });
    if (this.stepHistory.length > MAX_VISIBLE_STEPS) {
      yield* this.emitVisibleWindow();
    } else {
      yield* this.emitSlot(this.stepHistory.length - 1);
    }
  }

  private *updateStep(
    toolId: string,
    title: string,
    status: "pending" | "in_progress" | "complete" | "error",
  ): Generator<StreamChunk> {
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
      const entry = this.stepHistory[i];
      yield { type: "task_update", id: `step-${i - start}`, title: entry.title, status: entry.status };
    }
  }

  private planTitle = "";

  private *emitPlanTitle(activityTitle: string): Generator<StreamChunk> {
    const newTitle = truncate(activityTitle, 80);
    if (newTitle !== this.planTitle) {
      this.planTitle = newTitle;
      yield { type: "plan_update", title: newTitle };
    }
  }
}

// ── Tool labels ───────────────────────────────────────────────────────────

const TOOL_VERBS: Record<string, [active: string, done: string]> = {
  Read: ["Reading", "Read"],
  Bash: ["Running", "Ran"],
  Grep: ["Searching", "Searched"],
  glob: ["Finding files", "Found files"],
  finder: ["Searching codebase", "Searched codebase"],
  edit_file: ["Editing", "Edited"],
  create_file: ["Creating file", "Created file"],
  Task: ["Running subtask", "Ran subtask"],
  web_search: ["Searching the web", "Searched the web"],
  read_web_page: ["Reading webpage", "Read webpage"],
  librarian: ["Researching codebase", "Researched codebase"],
  oracle: ["Consulting oracle", "Consulted oracle"],
  mermaid: ["Drawing diagram", "Drew diagram"],
  look_at: ["Analyzing file", "Analyzed file"],
  skill: ["Loading skill", "Loaded skill"],
};

function friendlyToolLabel(name: string, input: Record<string, unknown>, done?: boolean): string {
  const pair = TOOL_VERBS[name];
  const verb = pair ? pair[done ? 1 : 0] : name;
  const ctx = friendlyToolContext(name, input);
  return ctx ? `${verb} — ${ctx}` : verb;
}

function friendlyToolContext(name: string, input: Record<string, unknown>): string {
  const str = (key: string) => (typeof input[key] === "string" ? (input[key] as string) : "");
  switch (name) {
    case "Read": case "edit_file": case "create_file": case "look_at":
      return shortPath(str("path"));
    case "Bash":
      return friendlyBashContext(str("cmd"));
    case "Grep":
      return truncate(str("pattern"), 50);
    case "glob":
      return truncate(str("filePattern"), 50);
    case "finder":
      return truncate(str("query"), 60);
    case "web_search":
      return truncate(str("objective"), 60);
    case "read_web_page":
      return truncate(str("url"), 60);
    case "Task":
      return truncate(str("description"), 60);
    case "skill":
      return str("name");
    default:
      return summarizeInput(input);
  }
}

function friendlyBashContext(cmd: string): string {
  if (!cmd) return "";
  const trimmed = cmd.trim();
  const callMatch = trimmed.match(/^call\s+(\S+)\s+(\S+)/);
  if (callMatch) return `${callMatch[1]}.${callMatch[2]}`;
  return truncate(trimmed, 60);
}

function shortPath(p: string): string {
  if (!p) return "";
  const parts = p.split("/");
  return parts.length <= 3 ? p : `…/${parts.slice(-2).join("/")}`;
}

function truncate(s: string, max: number): string {
  if (!s) return "";
  const line = s.replace(/\n/g, " ").trim();
  return line.length > max ? `${line.slice(0, max)}…` : line;
}

function summarizeInput(input: Record<string, unknown>): string {
  for (const key of ["query", "pattern", "command", "cmd", "prompt", "path", "url", "message"]) {
    if (typeof input[key] === "string") return `${key}: "${input[key]}"`;
  }
  for (const [key, val] of Object.entries(input)) {
    if (typeof val === "string" && val.length > 0) return `${key}: "${val}"`;
  }
  return "";
}

function simpleHash(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  }
  return (h >>> 0).toString(36);
}

function findLastIndex<T>(arr: T[], predicate: (item: T) => boolean): number {
  for (let i = arr.length - 1; i >= 0; i--) {
    if (predicate(arr[i])) return i;
  }
  return -1;
}
