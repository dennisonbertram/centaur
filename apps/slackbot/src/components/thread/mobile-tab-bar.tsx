"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutList, Zap } from "lucide-react";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";
import { useKeyboardHeight } from "@/hooks/use-visual-viewport";

type MobileTabBarProps = {
  activeThreadHref?: string;
  hasRunningAgent?: boolean;
  hasError?: boolean;
};

export function MobileTabBar({ activeThreadHref, hasRunningAgent, hasError }: MobileTabBarProps) {
  const pathname = usePathname();
  const keyboardHeight = useKeyboardHeight();
  const keyboardOpen = keyboardHeight > 0;
  const reduceMotion = useMediaQuery("(prefers-reduced-motion: reduce)");

  const isThreads = pathname === "/";
  const isActive = pathname.length > 1 && !pathname.startsWith("/api/");
  if (keyboardOpen) return null;

  function scrollCurrentViewToTop() {
    const behavior: ScrollBehavior = reduceMotion ? "auto" : "smooth";
    if (isThreads) {
      const list = document.querySelector<HTMLElement>("[data-thread-list-scroll='true']");
      if (list) {
        list.scrollTo({ top: 0, behavior });
        return;
      }
    }
    if (isActive) {
      const feed = document.querySelector<HTMLElement>("[data-thread-feed-scroll='true']");
      if (feed) {
        feed.scrollTo({ top: 0, behavior });
        return;
      }
    }
    window.scrollTo({ top: 0, behavior });
  }

  function handleThreadsTab() {
    if (isThreads) {
      scrollCurrentViewToTop();
      return;
    }
  }

  function handleActiveTab() {
    if (isActive) {
      scrollCurrentViewToTop();
      return;
    }
  }

  const threadsClassName = cn(
    "relative flex min-w-[88px] flex-col items-center justify-center gap-0.5 rounded-lg px-2.5 py-2.5 transition-colors duration-150",
    isThreads
      ? "border border-primary/40 bg-primary/14 text-primary"
      : "border border-transparent text-muted-foreground hover:bg-accent/40 hover:text-foreground",
  );
  const activeClassName = cn(
    "relative flex min-w-[88px] flex-col items-center justify-center gap-0.5 rounded-lg px-2.5 py-2.5 transition-colors duration-150",
    isActive
      ? "border border-primary/40 bg-primary/14 text-primary"
      : "border border-transparent text-muted-foreground hover:bg-accent/40 hover:text-foreground",
  );
  const activeHref = activeThreadHref || "/";

  return (
    <nav
      className={cn(
        "md:hidden flex-shrink-0 flex items-center justify-center border-t border-border/70 bg-[linear-gradient(180deg,color-mix(in_oklab,var(--background)_88%,transparent),color-mix(in_oklab,var(--card)_82%,transparent))] px-3 backdrop-blur-xl min-h-[66px] pb-[max(0.5rem,env(safe-area-inset-bottom))] transition-[opacity,transform] duration-[var(--dur-base)] ease-[var(--ease-standard)]",
      )}
      aria-label="Thread navigation"
    >
      <div className="thread-surface-soft flex w-full max-w-[360px] items-center justify-around rounded-xl p-1.5">
      {isThreads ? (
        <button
          type="button"
          aria-current="page"
          onClick={handleThreadsTab}
          className={threadsClassName}
        >
          <LayoutList className="size-5" />
          <span className="text-xs font-medium">Threads</span>
        </button>
      ) : (
        <Link href="/" scroll={false} aria-current={undefined} className={threadsClassName}>
          {hasError && !isThreads && (
            <span className="absolute top-1.5 right-3 size-1.5 rounded-full bg-destructive" />
          )}
          <LayoutList className="size-5" />
          <span className="text-xs font-medium">Threads</span>
        </Link>
      )}

      {isActive ? (
        <button
          type="button"
          aria-current="page"
          onClick={handleActiveTab}
          className={activeClassName}
        >
          {hasRunningAgent && (
            <span className="absolute top-1.5 right-3 size-2 rounded-full bg-primary animate-pulse motion-reduce:animate-none" />
          )}
          <Zap className="size-5" />
          <span className="text-xs font-medium">Active</span>
        </button>
      ) : (
        <Link href={activeHref} scroll={false} aria-current={undefined} className={activeClassName}>
          {hasRunningAgent && (
            <span className="absolute top-1.5 right-3 size-2 rounded-full bg-primary animate-pulse motion-reduce:animate-none" />
          )}
          <Zap className="size-5" />
          <span className="text-xs font-medium">Active</span>
        </Link>
      )}
      </div>
    </nav>
  );
}
