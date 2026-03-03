"use client";

import { Suspense, useEffect, useMemo, useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { LoaderCircle, RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useThreadList } from "@/hooks/use-thread-list";
import { useThreadPresence } from "@/hooks/use-thread-presence";
import { useMediaQuery } from "@/hooks/use-media-query";
import { MobileTabBar } from "@/components/thread/mobile-tab-bar";
import { runningSubtitle, type ThreadStatusFilter } from "@/lib/thread-selectors";
import { ThreadStatusTabs } from "@/components/thread/thread-status-tabs";
import { ThreadSummaryCard } from "@/components/thread/thread-summary-card";
import { type VisibleThreadStatusFilter } from "@/components/thread/thread-ui-constants";
import { detailHrefWithEntrySource, nextListQueryString, parseEntryAnchor } from "@/lib/thread-navigation";

function ThreadsPageContent() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const searchRef = useRef<HTMLInputElement>(null);
  const restoredAnchorRef = useRef<string | null>(null);
  const initialQuery = searchParams.get("q") ?? "";
  const initialStatus = (searchParams.get("status") as ThreadStatusFilter | null) ?? "all";
  const normalizedInitialStatus: VisibleThreadStatusFilter =
    initialStatus === "active" || initialStatus === "error" ? initialStatus : "all";
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
    statusFilter: normalizedInitialStatus,
  });
  const visibleStatusFilter: VisibleThreadStatusFilter =
    statusFilter === "active" || statusFilter === "error" ? statusFilter : "all";
  const reduceMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
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
    const nextQuery = searchParams.get("q") ?? "";
    const nextStatusRaw = (searchParams.get("status") as ThreadStatusFilter | null) ?? "all";
    const nextStatus: VisibleThreadStatusFilter =
      nextStatusRaw === "active" || nextStatusRaw === "error" ? nextStatusRaw : "all";
    if (nextQuery !== query) {
      setQuery(nextQuery);
    }
    if (nextStatus !== visibleStatusFilter) {
      setStatusFilter(nextStatus);
    }
  }, [query, searchParams, setQuery, setStatusFilter, visibleStatusFilter]);

  useEffect(() => {
    const entryAnchor = parseEntryAnchor(searchParams.get("entry_anchor"));
    if (!entryAnchor || restoredAnchorRef.current === entryAnchor) return;
    const target = Array.from(
      document.querySelectorAll<HTMLElement>("[data-thread-key]"),
    ).find((node) => node.dataset.threadKey === entryAnchor);
    if (!target) return;
    restoredAnchorRef.current = entryAnchor;
    target.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
    const next = new URLSearchParams(searchParams.toString());
    next.delete("entry_anchor");
    const nextQuery = next.toString();
    router.replace(nextQuery ? `${pathname}?${nextQuery}` : pathname, { scroll: false });
  }, [filteredThreads, pathname, reduceMotion, router, searchParams]);

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
      className="thin-scrollbar mx-auto flex-1 min-h-0 w-full max-w-[1240px] overflow-y-auto overscroll-contain px-4 py-4 md:px-8 md:py-8"
      style={{ WebkitOverflowScrolling: "touch" }}
    >
      <div className="thread-surface-soft mb-5 rounded-2xl p-4 md:p-5">
      <div className="flex items-center justify-between border-b border-border/70 pb-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">
            Threads
          </h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {`${activeCount} live agent${activeCount !== 1 ? "s" : ""}`}
          </p>
        </div>
        <Button
          type="button"
          onClick={() => void refreshThreads()}
          disabled={isRefreshing}
          aria-busy={isRefreshing}
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 border-border/80 bg-card/50 text-xs text-muted-foreground transition-colors duration-[var(--dur-fast)] ease-[var(--ease-standard)] hover:bg-accent hover:text-foreground disabled:cursor-default disabled:opacity-60"
        >
          <RefreshCw className={isRefreshing ? "size-3.5 animate-spin" : "size-3.5"} />
          {isRefreshing ? "Refreshing…" : "Refresh"}
        </Button>
      </div>
      </div>
      <div className="mt-4 mb-4 relative">
        <label htmlFor="thread-filter" className="sr-only">
          Filter threads
        </label>
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          id="thread-filter"
          name="thread-filter"
          aria-label="Filter threads"
          ref={searchRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filter threads… (/)"
          autoComplete="off"
          className="h-10 w-full max-w-[460px] border-input/80 bg-background/80 pl-9 pr-8 shadow-none focus-visible:ring-1"
        />
      </div>
      <div className="mb-4 overflow-x-auto">
        <ThreadStatusTabs
          density="comfortable"
          value={visibleStatusFilter}
          counts={{ all: counts.all, active: counts.active, error: counts.error }}
          onChange={setStatusFilter}
        />
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
            const href = detailHrefWithEntrySource(t.slack_thread_key, {
              source: "threads",
              listQuery: listQueryString,
              anchor: t.slack_thread_key,
            });
            const statusSubtitle = liveStatusByThread[t.slack_thread_key] ?? runningSubtitle(t);

            return (
              <ThreadSummaryCard
                key={t.slack_thread_key}
                thread={t}
                href={href}
                density="comfortable"
                statusSubtitle={statusSubtitle}
                linkProps={{
                  scroll: false,
                  onMouseEnter: () => router.prefetch(href),
                  "data-thread-key": t.slack_thread_key,
                }}
              />
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
