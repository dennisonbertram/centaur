"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  forwardRef,
  type KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useId,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { ChevronLeft, ChevronRight, RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ThreadStatusTabs } from "@/components/thread/thread-status-tabs";
import { ThreadSummaryCard } from "@/components/thread/thread-summary-card";
import { type VisibleThreadStatusFilter } from "@/components/thread/thread-ui-constants";
import { useThreadList } from "@/hooks/use-thread-list";
import { useThreadPresence } from "@/hooks/use-thread-presence";
import { cn } from "@/lib/utils";
import { detailHrefWithEntrySource, nextListQueryString } from "@/lib/thread-navigation";
import { isRunningState } from "@/lib/thread-ordering";
import { runningSubtitle, type ThreadStatusFilter } from "@/lib/thread-selectors";
import { isTextInputTarget } from "@/lib/thread-utils";

export type ThreadSidebarHandle = {
  focusSearch: () => void;
  focusSidebar: () => void;
};

type ThreadSidebarProps = {
  selectedThreadKey: string | null;
  collapsed: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  onNavigate?: () => void;
  showCollapseToggle?: boolean;
  active?: boolean;
};

export const ThreadSidebar = forwardRef<ThreadSidebarHandle, ThreadSidebarProps>(function ThreadSidebar(
  {
    selectedThreadKey,
    collapsed,
    onCollapsedChange,
    onNavigate,
    showCollapseToggle = true,
    active = true,
  },
  ref,
) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [focusedThreadKey, setFocusedThreadKey] = useState<string | null>(null);
  const filterId = useId();
  const searchRef = useRef<HTMLInputElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const cardRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const detailPrefetchAtRef = useRef<Record<string, number>>({});
  const initialQuery = searchParams.get("q") ?? "";
  const initialStatus = (searchParams.get("status") as ThreadStatusFilter | null) ?? "all";
  const normalizedInitialStatus: VisibleThreadStatusFilter =
    initialStatus === "active" || initialStatus === "error" ? initialStatus : "all";
  const {
    threads,
    filteredThreads: sortedThreads,
    counts,
    loading,
    isRefreshing,
    error,
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
  const sidebarQueryString = useMemo(() => {
    return nextListQueryString(new URLSearchParams(searchParams.toString()), {
      query,
      status: statusFilter,
    });
  }, [query, searchParams, statusFilter]);
  const shouldSyncUrl = active && pathname !== "/";

  useEffect(() => {
    if (!shouldSyncUrl) return;
    if (searchParams.toString() === sidebarQueryString) return;
    const next = sidebarQueryString ? `${pathname}?${sidebarQueryString}` : pathname;
    router.replace(next, { scroll: false });
  }, [pathname, router, searchParams, shouldSyncUrl, sidebarQueryString]);

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
    if (sortedThreads.length === 0) {
      setFocusedThreadKey(null);
      return;
    }
    const hasFocused = focusedThreadKey
      ? sortedThreads.some((thread) => thread.slack_thread_key === focusedThreadKey)
      : false;
    if (selectedThreadKey && sortedThreads.some((thread) => thread.slack_thread_key === selectedThreadKey)) {
      setFocusedThreadKey(selectedThreadKey);
      return;
    }
    if (!hasFocused) {
      setFocusedThreadKey(sortedThreads[0].slack_thread_key);
    }
  }, [focusedThreadKey, selectedThreadKey, sortedThreads]);

  const presenceThreads = useMemo(
    () => (active && !collapsed ? sortedThreads.filter((thread) => isRunningState(thread.state)).slice(0, 8) : []),
    [active, collapsed, sortedThreads],
  );
  const { liveStatusByThread } = useThreadPresence(presenceThreads);

  const activeCount = useMemo(
    () => threads.filter((thread) => isRunningState(thread.state)).length,
    [threads],
  );

  const prefetchThread = useCallback(
    (threadKey: string) => {
      const baseHref = `/${encodeURIComponent(threadKey)}`;
      const href = sidebarQueryString ? `${baseHref}?${sidebarQueryString}` : baseHref;
      router.prefetch(href);

      const now = Date.now();
      const previousAt = detailPrefetchAtRef.current[threadKey] ?? 0;
      if (now - previousAt < 15000) return;
      detailPrefetchAtRef.current[threadKey] = now;
      router.prefetch(`/${encodeURIComponent(threadKey)}`);
    },
    [router, sidebarQueryString],
  );

  useEffect(() => {
    if (!active || sortedThreads.length === 0) return;
    sortedThreads.slice(0, 5).forEach((thread) => prefetchThread(thread.slack_thread_key));
  }, [active, prefetchThread, sortedThreads]);

  const focusThreadAt = useCallback(
    (nextIndex: number) => {
      const next = sortedThreads[nextIndex];
      if (!next) return;
      setFocusedThreadKey(next.slack_thread_key);
      const node = cardRefs.current[next.slack_thread_key];
      node?.focus();
      node?.scrollIntoView({ block: "nearest" });
    },
    [sortedThreads],
  );

  const handleListKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLElement>) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isTextInputTarget(event.target)) return;
      if (sortedThreads.length === 0) return;

      const currentIndex = Math.max(
        0,
        sortedThreads.findIndex((thread) => thread.slack_thread_key === focusedThreadKey),
      );
      if (event.key === "ArrowDown" || event.key.toLowerCase() === "j") {
        event.preventDefault();
        focusThreadAt(Math.min(currentIndex + 1, sortedThreads.length - 1));
        return;
      }
      if (event.key === "ArrowUp" || event.key.toLowerCase() === "k") {
        event.preventDefault();
        focusThreadAt(Math.max(currentIndex - 1, 0));
        return;
      }
      if (event.key === "Home") {
        event.preventDefault();
        focusThreadAt(0);
        return;
      }
      if (event.key === "End") {
        event.preventDefault();
        focusThreadAt(sortedThreads.length - 1);
        return;
      }
    },
    [focusThreadAt, focusedThreadKey, sortedThreads],
  );

  useImperativeHandle(
    ref,
    () => ({
      focusSearch: () => {
        if (collapsed) {
          toggleRef.current?.focus();
          return;
        }
        searchRef.current?.focus();
      },
      focusSidebar: () => {
        if (collapsed) {
          toggleRef.current?.focus();
          return;
        }
        const selected =
          selectedThreadKey && cardRefs.current[selectedThreadKey]
            ? cardRefs.current[selectedThreadKey]
            : focusedThreadKey
              ? cardRefs.current[focusedThreadKey]
              : null;
        if (selected) {
          selected.focus();
          selected.scrollIntoView({ block: "nearest" });
          return;
        }
        searchRef.current?.focus();
      },
    }),
    [collapsed, focusedThreadKey, selectedThreadKey],
  );

  const canToggle = showCollapseToggle && Boolean(onCollapsedChange);

  if (collapsed) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-end p-2.5">
        {canToggle ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                ref={toggleRef}
                type="button"
                onClick={() => onCollapsedChange?.(false)}
                aria-label="Expand sidebar"
                variant="outline"
                size="icon"
                className="size-9 border-border text-muted-foreground transition-colors duration-[var(--dur-fast)] ease-[var(--ease-standard)] hover:bg-accent hover:text-foreground"
              >
                <ChevronRight className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Expand sidebar (Cmd+[)</TooltipContent>
          </Tooltip>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col" onKeyDown={handleListKeyDown}>
      <div className="border-b border-border/70 bg-background/70 px-3 py-3 backdrop-blur-md">
        <div className="thread-surface-soft rounded-xl p-2.5">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold tracking-tight text-foreground">Threads</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {activeCount} live agent{activeCount === 1 ? "" : "s"}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              onClick={() => void refreshThreads()}
              disabled={isRefreshing || !active}
              variant="outline"
              size="xs"
              className="gap-1 border-border/80 bg-card/60 px-2 text-xs text-muted-foreground transition-colors duration-[var(--dur-fast)] ease-[var(--ease-standard)] hover:bg-accent hover:text-foreground disabled:cursor-default disabled:opacity-60"
              aria-busy={isRefreshing}
            >
              <RefreshCw className={cn("size-3", isRefreshing ? "animate-spin" : "")} />
              {isRefreshing ? "Refreshing…" : "Refresh"}
            </Button>
            {canToggle ? (
              <Button
                ref={toggleRef}
                type="button"
                onClick={() => onCollapsedChange?.(true)}
                aria-label="Collapse sidebar"
                variant="outline"
                size="icon-sm"
                className="border-border/80 bg-card/60 text-muted-foreground transition-colors duration-[var(--dur-fast)] ease-[var(--ease-standard)] hover:bg-accent hover:text-foreground"
              >
                <ChevronLeft className="size-4" />
              </Button>
            ) : null}
          </div>
        </div>
        <div className="mt-2.5 relative">
          <label htmlFor={filterId} className="sr-only">
            Filter threads
          </label>
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            ref={searchRef}
            id={filterId}
            name={filterId}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter threads… (/)"
            autoComplete="off"
            className="h-9 border-input/80 bg-background/80 pl-8 pr-7 text-sm shadow-none focus-visible:ring-1"
          />
          <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-border/80 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
            /
          </span>
        </div>
        <ThreadStatusTabs
          className="mt-2.5"
          density="compact"
          value={visibleStatusFilter}
          counts={{ all: counts.all, active: counts.active, error: counts.error }}
          onChange={setStatusFilter}
        />
        </div>
      </div>

      <nav className="thread-sidebar-list thin-scrollbar flex-1 min-h-0 overflow-y-auto px-2.5 py-2.5" aria-label="Thread list">
        {loading ? (
          <div className="space-y-2 py-1">
            {[0, 1, 2].map((index) => (
              <div key={index} className="rounded-md border border-border bg-card px-2.5 py-2.5">
                <div className="h-3.5 w-5/6 rounded bg-secondary animate-pulse" />
                <div className="mt-1.5 h-3 w-2/3 rounded bg-secondary animate-pulse" />
                <div className="mt-1.5 h-3 w-4/5 rounded bg-secondary animate-pulse" />
              </div>
            ))}
          </div>
        ) : error && sortedThreads.length === 0 ? (
          <div className="space-y-2 py-8 text-center">
            <p className="text-xs text-destructive">{error}</p>
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
        ) : sortedThreads.length === 0 ? (
          <div className="py-10 text-center text-xs text-muted-foreground">
            No threads match your filter.
          </div>
        ) : (
          <ul className="space-y-2" role="list">
            {sortedThreads.map((thread) => {
              const href = detailHrefWithEntrySource(thread.slack_thread_key, {
                source: "threads",
                listQuery: sidebarQueryString,
                anchor: thread.slack_thread_key,
              });
              const statusSubtitle = liveStatusByThread[thread.slack_thread_key] ?? runningSubtitle(thread);
              const isSelected = selectedThreadKey === thread.slack_thread_key;
              const isFocused = focusedThreadKey === thread.slack_thread_key;

              return (
                <li key={thread.slack_thread_key}>
                  <ThreadSummaryCard
                    thread={thread}
                    href={href}
                    density="compact"
                    isSelected={isSelected}
                    statusSubtitle={statusSubtitle}
                    linkRef={(node) => {
                      cardRefs.current[thread.slack_thread_key] = node;
                    }}
                    linkProps={{
                      "aria-current": isSelected ? "page" : undefined,
                      tabIndex: isFocused ? 0 : -1,
                      onMouseEnter: () => prefetchThread(thread.slack_thread_key),
                      onFocus: () => {
                        setFocusedThreadKey(thread.slack_thread_key);
                        prefetchThread(thread.slack_thread_key);
                      },
                      onClick: () => {
                        setFocusedThreadKey(thread.slack_thread_key);
                        onNavigate?.();
                      },
                    }}
                  />
                </li>
              );
            })}
          </ul>
        )}
      </nav>
    </div>
  );
});
