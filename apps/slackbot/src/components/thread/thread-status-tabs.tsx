"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { THREAD_STATUS_FILTER_OPTIONS, type VisibleThreadStatusFilter } from "@/components/thread/thread-ui-constants";

type ThreadStatusTabsProps = {
  value: VisibleThreadStatusFilter;
  counts: Record<VisibleThreadStatusFilter, number>;
  onChange: (next: VisibleThreadStatusFilter) => void;
  density?: "compact" | "comfortable";
  className?: string;
};

export function ThreadStatusTabs({
  value,
  counts,
  onChange,
  density = "comfortable",
  className,
}: ThreadStatusTabsProps) {
  const compact = density === "compact";

  return (
    <div
      className={cn(
        compact
          ? "grid w-full grid-cols-3 gap-1.5 text-xs"
          : "inline-flex min-w-max items-center gap-1.5 rounded-xl border border-border/70 bg-card/45 p-1",
        className,
      )}
    >
      {THREAD_STATUS_FILTER_OPTIONS.map((option) => {
        const active = value === option.id;
        return (
          <Button
            key={option.id}
            type="button"
            onClick={() => onChange(option.id)}
            aria-pressed={active}
            variant="ghost"
            size="xs"
            className={cn(
              compact
                ? "h-auto rounded-md border border-border/70 bg-card/55 px-1.5 py-1 text-center text-muted-foreground transition-colors duration-[var(--dur-fast)] ease-[var(--ease-standard)] hover:bg-accent/60 hover:text-foreground"
                : "min-h-[36px] rounded-md border border-transparent px-3 text-xs font-medium text-muted-foreground transition-colors duration-[var(--dur-fast)] ease-[var(--ease-standard)] hover:bg-accent/60 hover:text-foreground",
              active &&
                (compact
                  ? "border-primary/55 bg-primary/16 text-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]"
                  : "border-primary/45 bg-primary/14 text-primary"),
            )}
          >
            {compact ? (
              <span className="inline-flex items-center gap-1.5">
                <span>{option.shortLabel}</span>
                <span className="rounded bg-background/80 px-1 py-0.5 text-[10px] leading-none text-muted-foreground">
                  {counts[option.id]}
                </span>
              </span>
            ) : (
              <span>
                {option.label} {counts[option.id]}
              </span>
            )}
          </Button>
        );
      })}
    </div>
  );
}
