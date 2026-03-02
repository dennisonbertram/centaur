"use client";

import {
  AlertTriangle,
  ArrowDownToLine,
  Bot,
  Check,
  ChevronRight,
  Copy,
  FileDiff,
  FilePenLine,
  LoaderCircle,
  MessagesSquare,
  Timer,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAutoScroll } from "@/hooks/use-auto-scroll";
import type { Step } from "@/lib/describe";
import type { Participant } from "@/lib/types";
import { MarkdownView } from "@/components/thread/markdown-view";
import { DiffCard } from "@/components/thread/diff-card";
import { StepGroup } from "@/components/thread/step-group";
import { TerminalCard } from "@/components/thread/terminal-card";
import { ThinkingDivider } from "@/components/thread/thinking-divider";

function CopyResultButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function copyResult() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button
      type="button"
      onClick={() => void copyResult()}
      aria-label="Copy result text"
      className="copy-btn ml-auto inline-flex items-center gap-1 rounded bg-secondary/80 text-muted-foreground text-[10px] px-2 py-1 transition-colors hover:text-foreground"
    >
      {copied ? <Check className="size-3 text-green-500" /> : <Copy className="size-3" />}
      <span className="md:hidden">{copied ? "Copied" : "Copy"}</span>
    </button>
  );
}

function sourceLabel(source?: string): string {
  const normalized = (source ?? "").trim().toLowerCase();
  if (!normalized) return "Unknown";
  if (normalized === "thread_ui") return "Thread Viewer";
  if (normalized === "slack") return "Slack";
  if (normalized === "slack_subscribed_message") return "Slack Thread";
  if (normalized === "api") return "API";
  return normalized.replace(/_/g, " ");
}

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words[1][0]}`.toUpperCase();
}

function subagentStatusLabel(status: string): string {
  const normalized = status.trim().toLowerCase();
  if (!normalized) return "Update";
  return normalized.replace(/_/g, " ");
}

function renderStep(
  step: Step,
  key: string,
  participantsById: Map<string, Participant>,
  turnDurationsById: Record<number, number>,
): React.ReactNode {
  if (step.type === "phase") {
    return (
      <div key={key} className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
        <FileDiff className="size-3 text-primary" />
        {step.phase}
      </div>
    );
  }
  if (step.type === "thinking") return <ThinkingDivider key={key} text={step.text} durationS={step.durationS} />;
  if (step.type === "subagent") {
    const normalizedStatus = step.status.trim().toLowerCase();
    const toneClass =
      normalizedStatus === "failed"
        ? "border-destructive/30 bg-destructive/10 text-destructive"
        : normalizedStatus === "completed" || normalizedStatus === "selected"
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
          : normalizedStatus === "cancelled"
            ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
            : "border-border bg-card text-foreground";
    const progressText =
      step.completed !== undefined && step.totalBranches !== undefined
        ? `${step.completed}/${step.totalBranches} done`
        : null;
    const usageText =
      step.totalTokens !== undefined
        ? `${Math.max(0, step.totalTokens).toLocaleString()} tok${
            step.costUsd !== null && step.costUsd !== undefined ? ` / $${step.costUsd.toFixed(4)}` : ""
          }`
        : null;
    return (
      <div key={key} className={`step-item rounded-sm border px-3 py-2 ${toneClass}`}>
        <div className="flex items-center gap-2 text-xs">
          <Bot className="size-3.5" />
          <span className="font-medium">{step.name || "Subagent"}</span>
          <span className="ml-auto rounded bg-background/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wide">
            {subagentStatusLabel(step.status)}
          </span>
        </div>
        <div className="mt-1 text-[11px] text-muted-foreground">
          {[step.phase, progressText].filter(Boolean).join(" • ") || "Parallel worker update"}
        </div>
        {usageText ? <div className="mt-1 text-[11px] text-muted-foreground">{usageText}</div> : null}
        {step.summary ? <div className="mt-1 text-xs">{step.summary}</div> : null}
        {step.error ? <div className="mt-1 text-xs font-medium">{step.error}</div> : null}
      </div>
    );
  }
  if (step.type === "tool-group") {
    return <StepGroup key={key} icon={step.icon} summary={step.summary} calls={step.calls} />;
  }
  if (step.type === "diff") {
    return <DiffCard key={key} file={step.file} lang={step.lang} oldStr={step.oldStr} newStr={step.newStr} />;
  }
  if (step.type === "terminal") {
    return (
      <TerminalCard
        key={key}
        description={step.description}
        command={step.command}
        output={step.output}
        exitCode={step.exitCode}
      />
    );
  }
  if (step.type === "file-changes") {
    return (
      <div key={key} className="step-item rounded-sm border border-border bg-card px-3 py-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1.5">
          <FilePenLine className="size-3.5 text-primary" />
          File changes
        </div>
        <div className="space-y-1">
          {step.changes.map((change, index) => (
            <div key={`${change.path}-${index}`} className="text-xs font-mono text-muted-foreground">
              {change.kind} {change.path}
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (step.type === "error") {
    return (
      <div key={key} className="step-item rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive flex items-center gap-2">
        <AlertTriangle className="size-4 shrink-0" />
        {step.message}
      </div>
    );
  }
  if (step.type === "user-message") {
    const participant = step.userId ? participantsById.get(step.userId) : undefined;
    const displayName = participant?.name || step.userId || "User";
    const turnDuration = step.turnId ? turnDurationsById[step.turnId] : undefined;
    return (
      <div key={key} className="step-item rounded-sm border-l-[3px] border-l-primary bg-primary/5 px-3 py-2.5">
        <div className="mb-1.5 flex items-center gap-2 text-xs text-muted-foreground">
          {participant?.avatar_url ? (
            <img src={participant.avatar_url} alt={displayName} className="size-[18px] rounded-full" />
          ) : (
            <div className="flex size-[18px] items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground">
              {initials(displayName)}
            </div>
          )}
          <span className="text-sm font-medium text-foreground">{displayName}</span>
          {typeof turnDuration === "number" ? (
            <span className="ml-auto inline-flex items-center gap-1 rounded bg-background/70 px-1.5 py-0.5 text-[10px] font-mono tabular-nums text-muted-foreground">
              <Timer className="size-3" />
              {Math.max(0, Math.round(turnDuration))}s
            </span>
          ) : null}
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
            {sourceLabel(step.source)}
          </span>
        </div>
        <div className="whitespace-pre-wrap text-sm text-foreground">{step.text}</div>
      </div>
    );
  }
  if (step.type === "context-group") {
    return (
      <details key={key} className="group step-item rounded-lg border border-border/40 bg-card/40">
        <summary className="list-none cursor-pointer px-3 py-2 min-h-[44px] flex items-center gap-2 text-xs text-muted-foreground [&::-webkit-details-marker]:hidden">
          <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" />
          {step.items.length} message{step.items.length === 1 ? "" : "s"} in thread
        </summary>
        <div className="space-y-2 px-3 pb-3">
          {step.items.map((item) => {
            const participant = item.userId ? participantsById.get(item.userId) : undefined;
            const displayName = participant?.name || item.userId || "Thread participant";
            return (
              <div key={item.id} className="rounded border border-border/50 bg-background px-2 py-1.5">
                <div className="mb-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                  <span className="text-foreground">{displayName}</span>
                  <span>{sourceLabel(item.source)}</span>
                </div>
                <div className="whitespace-pre-wrap text-xs text-muted-foreground">{item.text}</div>
              </div>
            );
          })}
        </div>
      </details>
    );
  }
  if (step.type === "result") {
    return (
      <div key={key} className="step-item rounded-sm border border-border bg-card px-3 py-2">
        <div className="flex items-center gap-2 mb-1 text-xs text-muted-foreground">
          <MessagesSquare className="size-3.5 text-primary" />
          Result
          <CopyResultButton text={step.text} />
        </div>
        <div className={`relative ${step.streaming ? "streaming-cursor" : ""}`}>
          <MarkdownView text={step.text} isStreaming={step.streaming} />
        </div>
      </div>
    );
  }
  return null;
}

export function ActivityFeed({
  steps,
  state,
  isStreaming,
  participants,
  turnDurationsById = {},
}: {
  steps: Step[];
  state?: string;
  isStreaming?: boolean;
  participants?: Participant[];
  turnDurationsById?: Record<number, number>;
}) {
  const activeCount = steps.length;
  const { containerRef, sentinelRef } = useAutoScroll([steps]);
  const [pendingSteps, setPendingSteps] = useState(0);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const previousCountRef = useRef(activeCount);
  const participantsById = useMemo(
    () => new Map((participants || []).map((participant) => [participant.id, participant])),
    [participants],
  );

  useEffect(() => {
    if (activeCount <= previousCountRef.current) {
      previousCountRef.current = activeCount;
      return;
    }
    const delta = activeCount - previousCountRef.current;
    previousCountRef.current = activeCount;
    if (!isNearBottom) {
      setPendingSteps((value) => value + delta);
    }
  }, [activeCount, isNearBottom]);

  function handleScroll() {
    const container = containerRef.current;
    if (!container) return;
    const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 120;
    setIsNearBottom(nearBottom);
    if (nearBottom) setPendingSteps(0);
  }

  function jumpToLatest() {
    sentinelRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    setPendingSteps(0);
  }

  const ariaLive = isStreaming ? "off" : "polite";

  return (
    <div className="relative flex-1 min-h-0">
      <div
        ref={containerRef}
        data-thread-feed-scroll="true"
        role="log"
        aria-live={ariaLive}
        aria-busy={isStreaming}
        onScroll={handleScroll}
        className="h-full overflow-y-auto overscroll-contain px-4 md:px-5 py-3 md:py-4 space-y-2.5 md:space-y-3"
        style={{ WebkitOverflowScrolling: "touch" }}
      >
      {activeCount === 0 ? (
        <div className="h-full flex items-center justify-center">
          <div className="flex flex-col items-center gap-2 text-center">
            {state === "idle" || state === "stopped" ? (
              <MessagesSquare className="size-8 text-muted-foreground/70" />
            ) : (
              <LoaderCircle className="size-8 text-muted-foreground/70 animate-spin" />
            )}
            <p className="text-sm text-foreground">
              {state === "idle" || state === "stopped" ? "No activity yet" : "Waiting for events"}
            </p>
            <p className="text-xs text-muted-foreground">
              {state === "idle" || state === "stopped"
                ? "Send a message below to start the agent."
                : "The agent is processing your request."}
            </p>
          </div>
        </div>
      ) : (
        steps.map((step, index) => renderStep(step, `live-${index}`, participantsById, turnDurationsById))
      )}
      <div ref={sentinelRef} className="h-px" />
      </div>
      {pendingSteps > 0 && (
        <button
          type="button"
          onClick={jumpToLatest}
          aria-label={`Jump to latest, ${pendingSteps} new step${pendingSteps === 1 ? "" : "s"}`}
          className="absolute right-4 rounded-full bg-primary text-primary-foreground shadow-lg px-3 py-2 text-xs font-medium min-h-[44px] flex items-center gap-1.5 cursor-pointer animate-in fade-in slide-in-from-bottom-2 duration-200"
          style={{ bottom: "max(1rem, calc(env(safe-area-inset-bottom) + 0.5rem))" }}
        >
          <ArrowDownToLine className="size-3.5" />
          {pendingSteps} new
        </button>
      )}
    </div>
  );
}
