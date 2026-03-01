"use client";

import { cn } from "@/lib/utils";

type ChipAction = {
  label: string;
  value: string;
  variant?: "default" | "destructive" | "primary";
};

type QuickActionChipsProps = {
  threadState: string;
  onAction: (value: string) => void;
  className?: string;
};

const CHIP_SETS: Record<string, ChipAction[]> = {
  running: [
    { label: "Stop agent", value: "stop", variant: "destructive" },
  ],
  waiting: [
    { label: "Yes, continue", value: "yes" },
    { label: "No", value: "no" },
    { label: "Explain more", value: "explain" },
  ],
  error: [
    { label: "Retry", value: "retry", variant: "primary" },
    { label: "Retry with context", value: "retry-context", variant: "primary" },
  ],
  stopped: [
    { label: "Resume", value: "resume", variant: "primary" },
  ],
};

const VARIANT_CLASSES: Record<string, string> = {
  default: "bg-secondary text-secondary-foreground border-border/50",
  destructive: "bg-destructive/10 text-destructive border-destructive/20",
  primary: "bg-primary/10 text-primary border-primary/20",
};

export function QuickActionChips({ threadState, onAction, className }: QuickActionChipsProps) {
  const normalizedState = threadState === "working" ? "running" : threadState;
  const chips = CHIP_SETS[normalizedState];
  if (!chips || chips.length === 0) return null;

  return (
    <div
      className={cn(
        "flex gap-2 overflow-x-auto px-3 py-1.5 border-t border-border/50",
        "scrollbar-none md:hidden",
        "animate-in slide-in-from-bottom-2 duration-200",
        className,
      )}
      style={{ WebkitOverflowScrolling: "touch" }}
    >
      {chips.map((chip) => (
        <button
          key={chip.value}
          type="button"
          onClick={() => onAction(chip.value)}
          className={cn(
            "inline-flex items-center whitespace-nowrap",
            "px-3 py-1.5 rounded-full text-xs font-medium",
            "border min-h-[44px] transition-colors",
            "active:opacity-80",
            VARIANT_CLASSES[chip.variant ?? "default"],
          )}
        >
          {chip.label}
        </button>
      ))}
    </div>
  );
}
