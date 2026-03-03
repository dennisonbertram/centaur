"use client";

import { Suspense, useEffect, useMemo, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { LoaderCircle, RefreshCw } from "lucide-react";
import { timeAgo } from "@/lib/format";
import { HarnessBadge } from "@/components/ui/harness-badge";
import { StateDot } from "@/components/ui/state-dot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ParticipantAvatars } from "@/components/thread/participant-avatars";
import { Progress } from "@/components/ui/progress";
import { PHASES } from "@/lib/types";
import { useElapsed } from "@/hooks/use-elapsed";
import { useThreadList } from "@/hooks/use-thread-list";
import { useThreadPresence } from "@/hooks/use-thread-presence";
import { MobileTabBar } from "@/components/thread/mobile-tab-bar";
import {
  getThreadDisplayName,
  parseActivePhase,
  runningSubtitle,
  type ThreadStatusFilter,
} from "@/lib/thread-selectors";
import { detailHrefWithEntrySource, nextListQueryString, parseEntryAnchor } from "@/lib/thread-navigation";

function ThreadAge({ thread }: { thread: { last_activity: number; state: string } }) {
  const isRunning = thread.state === "working" || thread.state === "running";
  const elapsed = useElapsed(thread.last_activity, isRunning);
  return <span>{isRunning ? elapsed : timeAgo(thread.last_activity)}</span>;
}

function ThreadsPageContent() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const searchRef = useRef<HTMLInputElement>(null);
  const restoredAnchorRef = useRef<string | null>(null);
  const initialQuery = searchParams.get("q") ?? "";
  const initialStatus = (searchParams.get("status") as ThreadStatusFilter | null) ?? "all";
  const {
    threads,
    filteredThreads,
    counts,
    loading,
    isRefreshing,
    error,
    activeCount,
    activeThreadHref,
    query,
    statusFilter,
    setQuery,
    setStatusFilter,
    refreshThreads,
  } = useThreadList({
    query: initialQuery,
    statusFilter: initialStatus,
  });
  const { liveStatusByThread } = useThreadPresence(filteredThreads);

  const listQueryString = useMemo(() => {
    return nextListQueryString(new URLSearchParams(searchParams.toString()), {
      query,
      status: statusFilter,
    });
  }, [query, searchParams, statusFilter]);

  useEffect(() => {
    if (searchParams.toString() === listQueryString) return;
    const next = listQueryString ? `${pathname}?${listQueryString}` : pathname;
    router.replace(next, { scroll: false });
  }, [listQueryString, pathname, router, searchParams]);

  useEffect(() => {
    const entryAnchor = parseEntryAnchor(searchParams.get("entry_anchor"));
    if (!entryAnchor || restoredAnchorRef.current === entryAnchor) return;
    const target = Array.from(
      document.querySelectorAll<HTMLElement>("[data-thread-key]"),
    ).find((node) => node.dataset.threadKey === entryAnchor);
    if (!target) return;
    restoredAnchorRef.current = entryAnchor;
    target.scrollIntoView({ block: "center", behavior: "smooth" });
    const next = new URLSearchParams(searchParams.toString());
    next.delete("entry_anchor");
    const nextQuery = next.toString();
    router.replace(nextQuery ? `${pathname}?${nextQuery}` : pathname, { scroll: false });
  }, [filteredThreads, pathname, router, searchParams]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "/") return;
      if (
        event.target instanceof HTMLElement &&
        event.target.closest("input, textarea, select, [contenteditable='true']")
      ) {
        return;
      }
      event.preventDefault();
      searchRef.current?.focus();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className="h-full flex flex-col bg-background text-foreground font-sans overflow-hidden">
    <div
      data-thread-list-scroll="true"
      className="mx-auto flex-1 min-h-0 w-full max-w-[1200px] overflow-y-auto overscroll-contain px-4 py-4 md:px-8 md:py-8"
      style={{ WebkitOverflowScrolling: "touch" }}
    >
      <div className="mb-6 flex items-center justify-between border-b border-border/80 pb-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">
            Threads
          </h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {`${activeCount} active agent${activeCount !== 1 ? "s" : ""}`}
          </p>
        </div>
        <Button
          type="button"
          onClick={() => void refreshThreads()}
          disabled={isRefreshing}
          aria-busy={isRefreshing}
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 border-border text-xs text-muted-foreground hover:bg-accent hover:text-foreground disabled:cursor-default disabled:opacity-60"
        >
          <RefreshCw className={isRefreshing ? "size-3.5 animate-spin" : "size-3.5"} />
          {isRefreshing ? "Refreshing…" : "Refresh"}
        </Button>
      </div>
      <div className="mb-4">
        <label htmlFor="thread-filter" className="sr-only">
          Filter threads
        </label>
        <Input
          id="thread-filter"
          name="thread-filter"
          aria-label="Filter threads"
          ref={searchRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filter threads… (/)"
          autoComplete="off"
          className="h-9 w-full max-w-[420px] bg-card shadow-none focus-visible:ring-1"
        />
      </div>
      <div className="mb-4 overflow-x-auto">
        <div className="inline-flex min-w-max items-center gap-2">
          <Button
            type="button"
            onClick={() => setStatusFilter("all")}
            aria-pressed={statusFilter === "all"}
            variant="outline"
            size="sm"
            className={`min-h-[36px] rounded-md px-3 text-xs font-medium transition-colors duration-150 ${
              statusFilter === "all"
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-secondary text-secondary-foreground border-border/50"
            }`}
          >
            All {counts.all}
          </Button>
          <Button
            type="button"
            onClick={() => setStatusFilter("active")}
            aria-pressed={statusFilter === "active"}
            variant="outline"
            size="sm"
            className={`min-h-[36px] rounded-md px-3 text-xs font-medium transition-colors duration-150 ${
              statusFilter === "active"
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-secondary text-secondary-foreground border-border/50"
            }`}
          >
            Active {counts.active}
          </Button>
          <Button
            type="button"
            onClick={() => setStatusFilter("error")}
            aria-pressed={statusFilter === "error"}
            variant="outline"
            size="sm"
            className={`min-h-[36px] rounded-md px-3 text-xs font-medium transition-colors duration-150 ${
              statusFilter === "error"
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-secondary text-secondary-foreground border-border/50"
            }`}
          >
            Error {counts.error}
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="text-muted-foreground text-center py-16 text-sm inline-flex items-center justify-center gap-2 w-full">
          <LoaderCircle className="size-4 animate-spin text-primary" />
          Loading…
        </div>
      ) : error && filteredThreads.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-destructive text-sm mb-3">{error}</p>
          <Button
            type="button"
            onClick={() => void refreshThreads()}
            variant="outline"
            size="xs"
            className="border-border text-xs text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            Retry
          </Button>
        </div>
      ) : filteredThreads.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-muted-foreground text-sm font-medium mb-1">
            No threads match this filter
          </p>
          <p className="text-muted-foreground text-xs">
            Mention @AI2 in a Slack thread to start one
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2.5 md:grid md:grid-cols-[repeat(auto-fill,minmax(360px,1fr))] md:gap-3">
          {filteredThreads.map((t) => {
            const name = getThreadDisplayName(t);
            const href = detailHrefWithEntrySource(t.slack_thread_key, {
              source: "threads",
              listQuery: listQueryString,
              anchor: t.slack_thread_key,
            });
            const rawTask = t.first_message || t.last_result || "";
            const taskPreview = rawTask.replace(/^\[[\w]+\]\s*/, "").slice(0, 100);
            const isActive = t.state === "working" || t.state === "running";
            const activePhase = parseActivePhase(t);
            const statusSubtitle = liveStatusByThread[t.slack_thread_key] ?? runningSubtitle(t);
            const phaseIndex = activePhase ? PHASES.indexOf(activePhase as (typeof PHASES)[number]) : -1;
            const progress = phaseIndex >= 0 ? ((phaseIndex + 1) / PHASES.length) * 100 : 0;

            return (
              <Link
                key={t.slack_thread_key}
                href={href}
                prefetch={false}
                scroll={false}
                onMouseEnter={() => router.prefetch(href)}
                aria-label={`View thread ${name}, ${t.state}, ${t.turn_count} turns`}
                data-thread-key={t.slack_thread_key}
                className={`block rounded-md border border-border/90 bg-card p-4 no-underline text-inherit shadow-[0_0_0_1px_rgba(255,255,255,0.02)] transition-[background-color,border-color,box-shadow,transform] duration-200 ease-out hover:bg-accent/65 hover:shadow-[0_0_0_1px_rgba(255,255,255,0.06)] active:scale-[0.997] ${
                  isActive ? "border-l-2 border-l-primary" : ""
                }`}
              >
                <div className="mb-2 flex min-w-0 items-center justify-between">
                  <div className="flex min-w-0 items-center gap-2">
                    <HarnessBadge harness={t.harness} />
                    <span className="text-sm text-foreground font-medium truncate">
                      {name}
                    </span>
                    <span className="hidden lg:inline-flex">
                      <ParticipantAvatars participants={t.participants} size={20} />
                    </span>
                  </div>
                  <StateDot state={t.state} />
                </div>

                <div className="mb-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span>
                    {t.turn_count} turn{t.turn_count !== 1 ? "s" : ""}
                  </span>
                  <span className="text-muted-foreground">·</span>
                  <ThreadAge thread={t} />
                </div>
                {statusSubtitle ? (
                  <div className="mb-1.5 text-xs text-muted-foreground">{statusSubtitle}</div>
                ) : null}

                {taskPreview && (
                  <div className="text-xs text-muted-foreground leading-relaxed line-clamp-1 mt-1">
                    {taskPreview}
                  </div>
                )}
                {activePhase ? <Progress value={progress} className="h-0.5 mt-3 bg-muted" /> : null}
              </Link>
            );
          })}
        </div>
      )}
    </div>
    <MobileTabBar
      activeThreadHref={activeThreadHref}
      hasRunningAgent={activeCount > 0}
      hasError={threads.some((t) => t.state === "error")}
    />
    </div>
  );
}

function ThreadsPageFallback() {
  return (
    <div className="h-full flex flex-col bg-background text-foreground font-sans overflow-hidden">
      <div
        data-thread-list-scroll="true"
        className="mx-auto flex-1 min-h-0 w-full max-w-[1200px] overflow-y-auto overscroll-contain px-4 py-4 md:px-8 md:py-8"
        style={{ WebkitOverflowScrolling: "touch" }}
      >
        <div className="text-muted-foreground text-center py-16 text-sm inline-flex items-center justify-center gap-2 w-full">
          <LoaderCircle className="size-4 animate-spin text-primary" />
          Loading…
        </div>
      </div>
    </div>
  );
}

export default function ThreadsPage() {
  return (
    <Suspense fallback={<ThreadsPageFallback />}>
      <ThreadsPageContent />
    </Suspense>
  );
}
