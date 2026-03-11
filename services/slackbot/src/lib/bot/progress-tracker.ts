import type { CanonicalEvent } from "@centaur/harness-events";
import type { StreamChunk } from "chat";

type ActiveTool = { name: string; input: Record<string, unknown>; startedAt: number };

export class ProgressTracker {
  lastAssistantText = "";
  resultText = "";
  private activeTools = new Map<string, ActiveTool>();
  private _pendingChunks: StreamChunk[] = [];

  update(event: CanonicalEvent): boolean {
    if (event.type === "assistant" && event.message?.content) {
      let changed = false;
      for (const block of event.message.content) {
        if (block.type === "tool_use") {
          this.activeTools.set(block.id, {
            name: block.name,
            input: block.input,
            startedAt: Date.now(),
          });
          changed = true;
          this._pendingChunks.push({
            type: "task_update",
            id: block.id,
            title: friendlyToolLabel(block.name, block.input),
            status: "in_progress",
          });
        } else if (block.type === "text" && block.text) {
          this.lastAssistantText = block.text;
        }
      }
      return changed;
    }

    if (event.type === "tool" && event.content) {
      let changed = false;
      for (const block of event.content) {
        const active = this.activeTools.get(block.tool_use_id);
        if (active) {
          this.activeTools.delete(block.tool_use_id);
          changed = true;
          this._pendingChunks.push({
            type: "task_update",
            id: block.tool_use_id,
            title: friendlyToolName(active.name),
            status: block.is_error ? "error" : "complete",
          });
        }
      }
      return changed;
    }

    if (event.type === "reasoning") {
      this._pendingChunks.push({
        type: "task_update",
        id: "reasoning",
        title: "Thinking…",
        status: "in_progress",
      });
      return true;
    }

    if (event.type === "subagent") {
      const label = `Subagent: ${event.name || "Subagent"}`;
      if (event.status === "started") {
        this._pendingChunks.push({
          type: "task_update",
          id: event.subagent_id,
          title: label,
          status: "in_progress",
        });
        return true;
      }
      if (event.status === "completed" || event.status === "failed") {
        this._pendingChunks.push({
          type: "task_update",
          id: event.subagent_id,
          title: label,
          status: event.status === "completed" ? "complete" : "error",
        });
        return true;
      }
      return false;
    }

    if (event.type === "result") {
      this.resultText = event.text;
      this._pendingChunks.push({
        type: "task_update",
        id: "reasoning",
        title: "Thinking…",
        status: "complete",
      });
      return true;
    }

    if (event.type === "error") {
      this._pendingChunks.push({
        type: "markdown_text",
        text: `Error: ${event.error || "Unknown error"}`,
      });
      return true;
    }

    // command_execution, file_change, usage, system — no visual update
    return false;
  }

  addHandoff(goal: string, _newThreadKey: string): void {
    this.activeTools.clear();
    this.lastAssistantText = "";
    this.resultText = "";
    this._pendingChunks.push({
      type: "task_update",
      id: `handoff-${Date.now()}`,
      title: `Handed off → ${goal}`,
      status: "complete",
    });
  }

  pendingChunks(): StreamChunk[] {
    const chunks = this._pendingChunks;
    this._pendingChunks = [];
    return chunks;
  }
}

const TOOL_VERBS: Record<string, string> = {
  Read: "Reading",
  Bash: "Running command",
  Grep: "Searching",
  glob: "Finding files",
  finder: "Searching codebase",
  edit_file: "Editing",
  create_file: "Creating file",
  Task: "Running subtask",
  web_search: "Searching the web",
  read_web_page: "Reading webpage",
  librarian: "Researching codebase",
  oracle: "Consulting oracle",
  mermaid: "Drawing diagram",
  look_at: "Analyzing file",
  skill: "Loading skill",
};

function friendlyToolName(name: string): string {
  return TOOL_VERBS[name] ?? name;
}

function friendlyToolLabel(name: string, input: Record<string, unknown>): string {
  const verb = TOOL_VERBS[name] ?? name;
  const ctx = friendlyToolContext(name, input);
  return ctx ? `${verb} — ${ctx}` : verb;
}

function friendlyToolContext(name: string, input: Record<string, unknown>): string {
  const str = (key: string) => (typeof input[key] === "string" ? (input[key] as string) : "");

  switch (name) {
    case "Read":
    case "edit_file":
    case "create_file":
    case "look_at":
      return shortPath(str("path"));
    case "Bash":
      return truncate(str("cmd"), 60);
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

function shortPath(p: string): string {
  if (!p) return "";
  const parts = p.split("/");
  if (parts.length <= 3) return p;
  return `…/${parts.slice(-2).join("/")}`;
}

function truncate(s: string, max: number): string {
  if (!s) return "";
  // Collapse to single line
  const line = s.replace(/\n/g, " ").trim();
  return line.length > max ? `${line.slice(0, max)}…` : line;
}

function summarizeInput(input: Record<string, unknown>): string {
  const keys = Object.keys(input);
  if (keys.length === 0) return "";

  // Common patterns: show the most useful parameter
  for (const key of ["query", "pattern", "command", "cmd", "prompt", "path", "url", "message"]) {
    if (typeof input[key] === "string") {
      return `${key}: "${input[key]}"`;
    }
  }

  // Fallback: show first string param
  for (const key of keys) {
    if (typeof input[key] === "string" && (input[key] as string).length > 0) {
      return `${key}: "${input[key]}"`;
    }
  }

  return "";
}
