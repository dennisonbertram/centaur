"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { LoaderCircle } from "lucide-react";
import { ActivityFeed } from "@/components/thread/activity-feed";
import { CommandPalette } from "@/components/thread/command-palette";
import { MessageInput } from "@/components/thread/message-input";
import { QuickActionChips } from "@/components/thread/quick-action-chips";
import { MobileTabBar } from "@/components/thread/mobile-tab-bar";
import { ThreadInfoSheet } from "@/components/thread/thread-info-sheet";
import { ThreadDetailHeader } from "@/components/thread/thread-detail-header";
import { useThreadLayout } from "@/components/thread/thread-layout";
import { threadName } from "@/lib/thread-name";
import { useThreadStream } from "@/hooks/use-thread-stream";
import { useElapsed } from "@/hooks/use-elapsed";
import { useStableStatus } from "@/hooks/use-stable-status";
import { BASE } from "@/lib/constants";
import type { ThreadSummary } from "@/lib/types";
import { toast } from "sonner";

export default function ThreadDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { openMobileSidebar, mobileSidebarOpen } = useThreadLayout();
  const threadKey = decodeURIComponent(params.id as string);
  const {
    thread,
    error,
    fetchThread,
    isReconnecting,
    agentStatus,
    tokenUsage,
    chatStatus,
    sendThreadMessage,
    liveSteps,
  } = useThreadStream(threadKey);
  const humanName = thread?.thread_name || threadName(threadKey);
  const [isInterrupting, setIsInterrupting] = useState(false);
  const [interruptError, setInterruptError] = useState<string | null>(null);
  const [infoOpen, setInfoOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [compactMode, setCompactMode] = useState(false);
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const closeInfoSheet = useCallback(() => setInfoOpen(false), []);
  const isEngineer = thread?.harness === "engineer";
  const isWaiting = thread?.state === "waiting";
  const isRunning =
    thread?.state === "running" || thread?.state === "working" || thread?.state === "stopping";
  const isStreaming = chatStatus === "submitted" || chatStatus === "streaming";
  const canInterrupt =
    !!thread && !isEngineer && (thread.state === "running" || thread.state === "working");
  const activeTurnStartedAt =
    thread && thread.turns.length > 0 ? thread.turns[thread.turns.length - 1]?.started_at : null;
  const elapsedAnchor = isRunning ? activeTurnStartedAt : thread?.last_activity;
  const liveElapsed = useElapsed(elapsedAnchor, Boolean(isRunning));
  const stableStatus = useStableStatus(agentStatus);
  const tokenTicker = tokenUsage
    ? `${tokenUsage.total_tokens.toLocaleString()} tok / ${
        tokenUsage.cost_usd === null ? "--" : `$${tokenUsage.cost_usd.toFixed(4)}`
      }${tokenUsage.estimated ? "~" : ""}`
    : "-- tok / --";
  const phases = liveSteps.flatMap((step) => (step.type === "phase" ? [step.phase] : []));
  const turnDurationsById = useMemo(() => {
    if (!thread) return {};
    return Object.fromEntries(thread.turns.map((turn) => [turn.turn_id, turn.duration_s]));
  }, [thread]);
  const latestUserMessage = thread?.turns[thread.turns.length - 1]?.user_message?.trim() ?? "";
  const retryMessage = latestUserMessage || "Please retry the previous request.";

  const inputMode = isRunning ? "running" as const
    : isWaiting ? "waiting" as const
    : thread?.state === "error" ? "error" as const
    : "idle" as const;

  const interruptRun = useCallback(async (): Promise<boolean> => {
    if (!thread || !canInterrupt || isInterrupting) return false;
    setInterruptError(null);
    setIsInterrupting(true);
    try {
      const res = await fetch(`${BASE}/api/agent/interrupt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slack_thread_key: threadKey }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data?.error) {
        const message =
          typeof data?.error === "string"
            ? data.error
            : `Interrupt failed${res.ok ? "" : ` (${res.status})`}.`;
        setInterruptError(message);
        return false;
      }
      fetchThread();
      return true;
    } finally {
      setIsInterrupting(false);
    }
  }, [canInterrupt, fetchThread, isInterrupting, thread, threadKey]);

  useEffect(() => {
    fetch(`${BASE}/api/threads`)
      .then((res) => res.json())
      .then((data) => setThreads(Array.isArray(data?.threads) ? data.threads : []))
      .catch(() => {});
  }, []);

  const handleSendMessage = useCallback(
    async (text: string) => {
      const route = isEngineer && isWaiting ? "reply" : "execute";
      if (route === "execute" && canInterrupt) {
        const interrupted = await interruptRun();
        if (!interrupted) return;
      }
      await sendThreadMessage(text, route);
    },
    [canInterrupt, interruptRun, isEngineer, isWaiting, sendThreadMessage],
  );

  const handleStopAgent = useCallback(async () => {
    await interruptRun();
  }, [interruptRun]);

  const handleQuickAction = useCallback((value: string) => {
    if (value === "stop") {
      void interruptRun();
    } else if (value === "retry") {
      void sendThreadMessage(retryMessage, "execute");
    } else if (value === "retry-context") {
      void sendThreadMessage(
        `${retryMessage}\n\nPlease retry with additional detail and include edge cases.`,
        "execute",
      );
    } else {
      void handleSendMessage(value);
    }
  }, [interruptRun, handleSendMessage, retryMessage, sendThreadMessage]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (infoOpen || mobileSidebarOpen) {
        return;
      }
      const targetIsInput =
        e.target instanceof HTMLElement &&
        e.target.closest("input, textarea, select, [contenteditable='true']");

      if (e.key === "Escape") {
        if (targetIsInput) {
          (e.target as HTMLElement | null)?.blur?.();
          return;
        }
        e.preventDefault();
        router.push("/threads", { scroll: false });
        return;
      }

      if (targetIsInput) return;

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
        return;
      }

      if ((e.metaKey || e.ctrlKey) && e.key === ".") {
        e.preventDefault();
        setCompactMode((value) => !value);
        return;
      }

      if (e.shiftKey && e.key === "?") {
        e.preventDefault();
        toast("Shortcuts: Cmd/Ctrl+K, R, S, /, Esc, Cmd+., Shift+?");
        return;
      }

      if (e.key.toLowerCase() === "r") {
        e.preventDefault();
        fetchThread();
        return;
      }

      if (e.key.toLowerCase() === "s" && canInterrupt) {
        e.preventDefault();
        void interruptRun();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [canInterrupt, fetchThread, infoOpen, interruptRun, mobileSidebarOpen, router]);

  useEffect(() => {
    if (!thread) return;
    const previousTitle = document.title;
    if (thread.state === "working" || thread.state === "running") {
      document.title = `Working - ${humanName}`;
    } else if (thread.state === "waiting") {
      document.title = `Input needed - ${humanName}`;
    } else if (thread.state === "error") {
      document.title = `Error - ${humanName}`;
    } else {
      document.title = `Done - ${humanName}`;
    }
    return () => {
      document.title = previousTitle;
    };
  }, [humanName, thread]);

  if (error && !thread) {
    return (
      <div className="h-dvh md:h-full flex items-center justify-center bg-background">
        <div className="text-center">
          <p className="text-destructive text-sm mb-4">{error}</p>
          <div className="flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={fetchThread}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer bg-transparent border border-border rounded-sm px-3 py-1"
            >
              Retry
            </button>
            <Link
              href="/threads"
              className="text-muted-foreground text-xs hover:text-foreground transition-colors rounded-sm"
            >
              Back to threads
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!thread) {
    return (
      <div className="h-dvh md:h-full flex items-center justify-center bg-background">
        <div className="text-center">
          <p className="text-muted-foreground text-sm inline-flex items-center gap-2">
            <LoaderCircle className="size-4 animate-spin text-primary" />
            Connecting...
          </p>
          <p className="text-muted-foreground text-xs font-mono mt-2">{threadName(threadKey)}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-dvh md:h-full flex flex-col bg-background overflow-hidden">
      <ThreadDetailHeader
        thread={thread}
        humanName={humanName}
        tokenUsage={tokenUsage}
        tokenTicker={tokenTicker}
        liveElapsed={liveElapsed}
        stableStatus={stableStatus}
        isRunning={isRunning}
        isWaiting={isWaiting}
        isEngineer={isEngineer}
        phases={phases}
        isReconnecting={isReconnecting}
        error={error}
        interruptError={interruptError}
        canInterrupt={canInterrupt}
        isInterrupting={isInterrupting}
        onInterrupt={() => void interruptRun()}
        onRefresh={() => void fetchThread()}
        onOpenInfo={() => setInfoOpen(true)}
        onOpenDrawer={openMobileSidebar}
      />

      {/* Activity feed - the only scrollable area */}
      <div className="flex-1 min-h-0 max-w-[960px] mx-auto w-full flex flex-col">
        <ActivityFeed
          steps={liveSteps}
          state={thread.state}
          isStreaming={isStreaming}
          participants={thread.participants}
          turnDurationsById={turnDurationsById}
        />
      </div>

      {/* Quick action chips (mobile only) */}
      <QuickActionChips threadState={thread.state} onAction={handleQuickAction} />

      {/* Message input - always visible */}
      <MessageInput
        mode={inputMode}
        onSend={handleSendMessage}
        onStop={canInterrupt ? handleStopAgent : undefined}
      />

      {/* Mobile tab bar */}
      <MobileTabBar
        activeThreadHref={`/threads/${encodeURIComponent(threadKey)}`}
        hasRunningAgent={isRunning}
        hasError={thread.state === "error"}
      />

      {/* Overlays */}
      {thread && (
        <ThreadInfoSheet
          open={infoOpen}
          onClose={closeInfoSheet}
          thread={thread}
          tokenUsage={tokenUsage}
          elapsed={liveElapsed}
          onRefresh={fetchThread}
          onStop={canInterrupt ? interruptRun : undefined}
          canStop={canInterrupt}
        />
      )}

      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        threads={threads}
        currentThreadKey={threadKey}
        compactMode={compactMode}
        canInterrupt={canInterrupt}
        isRefreshing={false}
        onNavigate={(nextThreadKey) => router.push(`/threads/${encodeURIComponent(nextThreadKey)}`, { scroll: false })}
        onRefresh={() => void fetchThread()}
        onStop={() => void interruptRun()}
        onCopyUrl={() => {
          navigator.clipboard
            ?.writeText(window.location.href)
            .then(() => toast("Copied link"))
            .catch(() => {});
        }}
        onToggleCompact={() => setCompactMode((value) => !value)}
        onOpenSlack={thread.slack_thread_key.includes(":")
          ? () => {
              const [channel, ts] = thread.slack_thread_key.replace(/^slack:/, "").split(":");
              window.open(`slack://app_redirect?channel=${channel}&thread_ts=${ts}`, "_blank");
            }
          : null}
        onOpenShortcuts={() => toast("Shortcuts: Cmd/Ctrl+K, R, S, /, Esc, Cmd+., Shift+?")}
      />
    </div>
  );
}
