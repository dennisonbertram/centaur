"use client";

import { useEffect, useMemo, useState, type ComponentType } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUp,
  Bot,
  Brain,
  CircleStop,
  FilePenLine,
  FileText,
  Globe,
  Info,
  Menu,
  RefreshCw,
  SearchCode,
  SquareTerminal,
  Timer,
} from "lucide-react";
import type { ThreadDetail } from "@/lib/types";
import { HarnessBadge } from "@/components/ui/harness-badge";
import { StateDot } from "@/components/ui/state-dot";
import { ParticipantAvatars } from "@/components/thread/participant-avatars";
import { PhaseProgress } from "@/components/thread/phase-progress";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type TokenUsage = {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number | null;
  estimated: boolean;
  authoritative?: boolean;
  model: string | null;
};

type ThreadDetailHeaderProps = {
  thread: ThreadDetail;
  humanName: string;
  tokenUsage: TokenUsage | null;
  tokenTicker: string;
  liveElapsed: string;
  stableStatus: string | null;
  isRunning: boolean;
  isEngineer: boolean;
  phases: string[];
  isReconnecting: boolean;
  error: string | null;
  interruptError: string | null;
  canInterrupt: boolean;
  isInterrupting: boolean;
  onInterrupt: () => void;
  onRefresh: () => void;
  onOpenInfo: () => void;
  onOpenDrawer: () => void;
  sourceLabel: string;
  onBack: () => void;
  upHref: string;
};

function normalizeStatusLabel(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function categorizeStatus(status: string | null): {
  icon: ComponentType<{ className?: string }>;
  text: string;
} {
  const raw = normalizeStatusLabel(status ?? "");
  const lower = raw.toLowerCase();
  if (!raw) return { icon: Bot, text: "Working" };
  if (/search|grep|find/.test(lower)) return { icon: SearchCode, text: raw };
  if (/read|reading/.test(lower)) return { icon: FileText, text: raw };
  if (/edit|write|creat/.test(lower)) return { icon: FilePenLine, text: raw };
  if (/run|shell|command/.test(lower)) return { icon: SquareTerminal, text: raw };
  if (/fetch|web/.test(lower)) return { icon: Globe, text: raw };
  if (/think|reason/.test(lower)) return { icon: Brain, text: raw };
  return { icon: Bot, text: raw };
}

export function ThreadDetailHeader({
  thread,
  humanName,
  tokenUsage,
  tokenTicker,
  liveElapsed,
  stableStatus,
  isRunning,
  isEngineer,
  phases,
  isReconnecting,
  error,
  interruptError,
  canInterrupt,
  isInterrupting,
  onInterrupt,
  onRefresh,
  onOpenInfo,
  onOpenDrawer,
  sourceLabel,
  onBack,
  upHref,
}: ThreadDetailHeaderProps) {
  const [showReconnectBar, setShowReconnectBar] = useState(false);
  const usageConfidenceLabel = tokenUsage
    ? (tokenUsage.authoritative ?? !tokenUsage.estimated)
      ? "authoritative"
      : "estimated"
    : "--";
  const showError = !!error && !(thread.state === "error" && error.startsWith("Stream disconnected."));
  const statusSummary = useMemo(() => {
    if (thread.state === "error") return { icon: Bot, text: error || "Agent encountered an error" };
    if (thread.state === "stopping") return { icon: Bot, text: "Stopping run…" };
    if (isRunning) return categorizeStatus(stableStatus);
    return { icon: Bot, text: "Idle" };
  }, [error, isRunning, stableStatus, thread.state]);

  useEffect(() => {
    if (!isReconnecting || thread.state === "error") {
      setShowReconnectBar(false);
      return;
    }
    const timeout = window.setTimeout(() => setShowReconnectBar(true), 2000);
    return () => window.clearTimeout(timeout);
  }, [isReconnecting, thread.state]);

  return (
    <div className="relative shrink-0 border-b border-border/90 bg-background/95 backdrop-blur-md">
      {showReconnectBar ? <div className="reconnect-bar" aria-hidden="true" /> : null}
      <div className="flex h-11 items-center gap-2 px-3">
        <button
          type="button"
          onClick={onOpenDrawer}
          className="flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground md:hidden"
          aria-label="Open thread list"
        >
          <Menu className="size-5" />
        </button>

        <button
          type="button"
          onClick={onBack}
          aria-label="Back to source"
          className="mr-1 inline-flex items-center rounded-md p-1 text-xs text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
        </button>

        <Link
          href={upHref}
          scroll={false}
          aria-label="Up to threads"
          className="hidden rounded-md p-1 md:inline-flex items-center text-xs text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground"
        >
          <ArrowUp className="size-3.5" />
        </Link>

        <HarnessBadge harness={thread.harness} className="flex-shrink-0" />

        <span className="min-w-0 flex-1 truncate text-sm font-medium tracking-tight">{humanName}</span>

        <StateDot state={thread.state} className="flex-shrink-0" />
        <span className="hidden text-xs text-muted-foreground min-[380px]:inline">{thread.state}</span>

        <span className="hidden md:inline-flex">
          <ParticipantAvatars participants={thread.participants} size={20} />
        </span>
        <span className="hidden text-xs text-muted-foreground lg:inline">
          {thread.turns.length} turn{thread.turns.length === 1 ? "" : "s"}
        </span>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="hidden text-xs font-mono tabular-nums text-muted-foreground xl:inline">
              {tokenTicker}
            </span>
          </TooltipTrigger>
          <TooltipContent>
            <div className="space-y-0.5 text-xs">
              <div>Input: {tokenUsage?.input_tokens?.toLocaleString() ?? "--"}</div>
              <div>Output: {tokenUsage?.output_tokens?.toLocaleString() ?? "--"}</div>
              <div>Model: {tokenUsage?.model ?? "--"}</div>
              <div>Usage: {usageConfidenceLabel}</div>
            </div>
          </TooltipContent>
        </Tooltip>
        <span className="hidden items-center gap-1 text-xs font-mono tabular-nums text-muted-foreground lg:inline-flex">
          <Timer className="size-3.5" />
          {liveElapsed}
        </span>
        <span className="hidden text-xs font-mono text-muted-foreground xl:inline" title="Open command palette">
          Cmd+K
        </span>

        <button
          type="button"
          onClick={onOpenInfo}
          className="flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground md:hidden"
          aria-label="Thread info"
        >
          <Info className="size-4" />
        </button>

        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="hidden rounded-md p-1 text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground md:block"
              aria-label="Show thread metadata"
            >
              <Info className="size-3.5" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-[320px]">
            <div className="space-y-2 text-xs">
              <div className="font-semibold text-foreground">Debug IDs</div>
              <div className="font-mono text-muted-foreground break-all">{thread.slack_thread_key}</div>
              {thread.agent_thread_id ? (
                <div className="font-mono text-muted-foreground break-all">{thread.agent_thread_id}</div>
              ) : null}
            </div>
          </PopoverContent>
        </Popover>

        {canInterrupt && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={onInterrupt}
                disabled={isInterrupting}
                className="hidden rounded-md px-1 py-0.5 md:inline-flex items-center gap-1 text-xs text-destructive transition-colors duration-150 hover:bg-destructive/10 disabled:opacity-60"
              >
                <CircleStop className={isInterrupting ? "size-3.5 animate-pulse" : "size-3.5"} />
                {isInterrupting ? "Stopping…" : "Stop"}
              </button>
            </TooltipTrigger>
            <TooltipContent>Stop S</TooltipContent>
          </Tooltip>
        )}
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={onRefresh}
              className="hidden rounded-md px-1 py-0.5 md:inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground"
            >
              <RefreshCw className="size-3.5" />
              Refresh
            </button>
          </TooltipTrigger>
          <TooltipContent>Refresh R</TooltipContent>
        </Tooltip>
      </div>

      <div className="flex h-7 items-center gap-2 border-t border-border/50 px-3 text-xs">
        <span className="rounded-md bg-secondary px-1.5 py-0.5 text-xs text-muted-foreground">
          {sourceLabel}
        </span>
        <statusSummary.icon className="size-3.5 text-muted-foreground" />
        <span className={thread.state === "error" ? "text-destructive truncate" : "text-muted-foreground truncate"}>
          {statusSummary.text}
        </span>
        {isReconnecting ? (
          <span className="ml-auto text-xs text-primary">Reconnecting…</span>
        ) : null}
        {isRunning && tokenUsage?.model ? (
          <span className="hidden font-mono text-xs text-muted-foreground md:inline">
            {tokenUsage.model}
          </span>
        ) : null}
      </div>

      {(showError || !!interruptError) && (
        <div role="alert" className="inline-flex items-center gap-1.5 border-t border-border/50 px-3 py-1.5 text-xs text-destructive">
          <RefreshCw className="size-3.5" />
          {interruptError ??
            (thread.state === "error" && error?.startsWith("Stream disconnected.") ? null : error)}
        </div>
      )}

      {isEngineer && phases.length > 0 && (
        <div className="px-3 py-1.5 border-t border-border/50">
          <PhaseProgress phases={phases} />
        </div>
      )}
    </div>
  );
}
