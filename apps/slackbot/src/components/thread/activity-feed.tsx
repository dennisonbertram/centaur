"use client";

import {
  AlertTriangle,
  ArrowDown,
  Check,
  ChevronRight,
  Copy,
  FileDiff,
  FilePenLine,
  MessagesSquare,
  TerminalSquare,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
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

function renderStep(
  step: Step,
  key: string,
  participantsById: Map<string, Participant>,
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
    return (
      <div key={key} className="step-item rounded-lg border border-border/50 bg-card/50 p-3">
        <div className="mb-1.5 flex items-center gap-2 text-xs text-muted-foreground">
          {participant?.avatar_url ? (
            <img src={participant.avatar_url} alt={displayName} className="size-[18px] rounded-full" />
          ) : (
            <div className="flex size-[18px] items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground">
              {initials(displayName)}
            </div>
          )}
          <span className="text-sm font-medium text-foreground">{displayName}</span>
          <span className="ml-auto rounded bg-muted px-1.5 py-0.5 text-[10px]">
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
        <div className="relative">
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
}: {
  steps: Step[];
  state?: string;
  isStreaming?: boolean;
  participants?: Participant[];
}) {
  const activeCount = steps.length;
  const { containerRef, sentinelRef } = useAutoScroll([steps]);
  const [pendingSteps, setPendingSteps] = useState(0);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const previousCountRef = useRef(activeCount);
  const participantsById = new Map((participants || []).map((participant) => [participant.id, participant]));

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
        onScroll={handleScroll}
        className="h-full overflow-y-auto overscroll-contain px-4 md:px-5 py-3 md:py-4 space-y-1.5 md:space-y-4"
        style={{ WebkitOverflowScrolling: "touch" }}
      >
      {activeCount === 0 ? (
        <div className="h-full flex items-center justify-center text-sm text-muted-foreground gap-2">
          <TerminalSquare className="size-4 text-primary" />
          {state === "idle" ? "No events yet. This thread is idle." : "Waiting for events\u2026"}
        </div>
      ) : (
        steps.map((step, index) => renderStep(step, `live-${index}`, participantsById))
      )}
      <div ref={sentinelRef} className="h-px" />
      </div>
      {pendingSteps > 0 && (
        <button
          type="button"
          onClick={jumpToLatest}
          aria-label={`Jump to latest, ${pendingSteps} new step${pendingSteps === 1 ? "" : "s"}`}
          className="absolute bottom-4 right-4 rounded-full bg-primary text-primary-foreground shadow-lg px-3 py-2 text-xs font-medium min-h-[36px] flex items-center gap-1.5 cursor-pointer animate-in fade-in duration-200"
        >
          <ArrowDown className="size-3.5" />
          {pendingSteps} new
        </button>
      )}
    </div>
  );
}
