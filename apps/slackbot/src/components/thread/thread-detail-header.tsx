"use client";

import Link from "next/link";
import { ArrowLeft, CircleStop, Info, Menu, RefreshCw, Timer } from "lucide-react";
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
  isWaiting: boolean;
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
};

export function ThreadDetailHeader({
  thread,
  humanName,
  tokenUsage,
  tokenTicker,
  liveElapsed,
  stableStatus,
  isRunning,
  isWaiting,
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
}: ThreadDetailHeaderProps) {
  const showReconnect = isReconnecting && thread.state !== "error";
  const showError = !!error && !(thread.state === "error" && error.startsWith("Stream disconnected."));

  return (
    <div className="shrink-0 border-b border-border bg-background/95 backdrop-blur-xl">
      <div className="h-[48px] px-3 flex items-center gap-2">
        <button
          type="button"
          onClick={onOpenDrawer}
          className="size-9 flex items-center justify-center rounded-md active:bg-accent md:hidden"
          aria-label="Open thread list"
        >
          <Menu className="size-5" />
        </button>

        <Link
          href="/threads"
          scroll={false}
          aria-label="Back to threads"
          className="hidden md:flex text-muted-foreground text-xs hover:text-foreground transition-colors mr-1 rounded-sm"
        >
          <ArrowLeft className="size-4" />
        </Link>

        <HarnessBadge harness={thread.harness} className="flex-shrink-0" />

        <span className="text-sm font-medium truncate flex-1 min-w-0">{humanName}</span>

        <StateDot state={thread.state} className="flex-shrink-0" />
        <span className="text-[10px] text-muted-foreground hidden min-[380px]:inline">{thread.state}</span>

        <span className="hidden md:inline-flex">
          <ParticipantAvatars participants={thread.participants} size={20} />
        </span>
        <span className="text-[11px] text-muted-foreground hidden md:inline">
          {thread.turns.length} turn{thread.turns.length === 1 ? "" : "s"}
        </span>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="text-[11px] text-muted-foreground font-mono hidden md:inline">{tokenTicker}</span>
          </TooltipTrigger>
          <TooltipContent>
            <div className="space-y-0.5 text-xs">
              <div>Input: {tokenUsage?.input_tokens?.toLocaleString() ?? "--"}</div>
              <div>Output: {tokenUsage?.output_tokens?.toLocaleString() ?? "--"}</div>
              <div>Model: {tokenUsage?.model ?? "--"}</div>
            </div>
          </TooltipContent>
        </Tooltip>
        <span className="text-[11px] text-muted-foreground items-center gap-1 hidden md:inline-flex">
          <Timer className="size-3.5" />
          {liveElapsed}
        </span>
        <span className="text-[10px] text-muted-foreground font-mono hidden sm:inline" title="Press Esc to go back">
          esc
        </span>

        <button
          type="button"
          onClick={onOpenInfo}
          className="size-9 flex items-center justify-center rounded-md active:bg-accent md:hidden"
          aria-label="Thread info"
        >
          <Info className="size-4" />
        </button>

        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer hidden md:block"
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
          <button
            type="button"
            onClick={onInterrupt}
            disabled={isInterrupting}
            className="hidden md:inline-flex items-center gap-1 text-[11px] text-destructive hover:opacity-80 disabled:opacity-60 transition-colors cursor-pointer bg-transparent border-none p-0 rounded-sm"
          >
            <CircleStop className={isInterrupting ? "size-3.5 animate-pulse" : "size-3.5"} />
            {isInterrupting ? "Stopping..." : "Stop"}
          </button>
        )}
        <button
          type="button"
          onClick={onRefresh}
          className="hidden md:inline-flex text-muted-foreground text-[11px] hover:text-foreground transition-colors cursor-pointer bg-transparent border-none p-0 rounded-sm items-center gap-1"
        >
          <RefreshCw className="size-3.5" />
          Refresh
        </button>
      </div>

      {stableStatus && isRunning && (
        <div className="h-[24px] px-3 text-[11px] text-muted-foreground truncate border-t border-border/50 flex items-center animate-in fade-in duration-300">
          {stableStatus}
        </div>
      )}
      {isWaiting && (
        <div className="h-[24px] px-3 text-[11px] text-amber-400 truncate border-t border-border/50 flex items-center">
          Waiting for your reply
        </div>
      )}
      {thread.state === "error" && (
        <div className="h-[24px] px-3 text-[11px] text-destructive truncate border-t border-border/50 flex items-center">
          {error || "Agent encountered an error"}
        </div>
      )}

      {(showError || !!interruptError || showReconnect) && (
        <div className="px-3 py-1.5 text-[11px] text-amber-300 inline-flex items-center gap-1.5 border-t border-border/50">
          <RefreshCw className={isReconnecting ? "size-3.5 animate-spin" : "size-3.5"} />
          {interruptError ??
            (thread.state === "error" && error?.startsWith("Stream disconnected.") ? null : error) ??
            (isReconnecting ? "Reconnecting stream..." : "")}
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
