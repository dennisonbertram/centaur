"use client";

import { Check, ChevronRight, CircleCheck, CircleX, Terminal, X as XIcon } from "lucide-react";

export function TerminalCard({
  description,
  command,
  output,
  exitCode,
}: {
  description: string;
  command: string;
  output?: string;
  exitCode?: number;
}) {
  const ok = exitCode === 0;
  const failed = typeof exitCode === "number" && exitCode !== 0;
  return (
    <details className="group step-item rounded-lg md:rounded-sm border border-border/30 md:border-border bg-secondary/30 md:bg-card">
      <summary className="list-none cursor-pointer px-3 py-2 min-h-[44px] md:min-h-0 flex items-center gap-2 active:bg-secondary/60 md:active:bg-transparent [&::-webkit-details-marker]:hidden">
        {/* Mobile: status icon; Desktop: chevron */}
        <span className="md:hidden flex-shrink-0">
          {failed ? <XIcon className="size-4 text-destructive" /> :
           ok ? <Check className="size-4 text-green-500" /> :
           <Terminal className="size-4 text-muted-foreground" />}
        </span>
        <ChevronRight className="size-3.5 text-muted-foreground transition-transform group-open:rotate-90 hidden md:block" />
        <span className="text-sm truncate flex-1 min-w-0 text-muted-foreground md:text-foreground">{description}</span>
        {typeof exitCode === "number" && (
          <span className="ml-auto inline-flex items-center gap-1 text-xs flex-shrink-0 hidden md:inline-flex">
            {ok ? (
              <CircleCheck className="size-3.5 text-primary" />
            ) : (
              <CircleX className="size-3.5 text-destructive" />
            )}
            <span className={ok ? "text-primary" : "text-destructive"}>exit {exitCode}</span>
          </span>
        )}
        <ChevronRight className="size-4 text-muted-foreground/50 transition-transform group-open:rotate-90 flex-shrink-0 md:hidden" />
      </summary>
      <div className="border-t border-border/20 md:border-border px-3 py-2 space-y-2">
        <pre className="rounded-sm bg-background p-2 text-[11px] text-foreground overflow-auto whitespace-pre-wrap">
          $ {command}
        </pre>
        {output && (
          <pre className="rounded-sm bg-background p-2 text-[11px] text-muted-foreground overflow-auto max-h-[240px] md:max-h-[320px] whitespace-pre-wrap">
            {output}
          </pre>
        )}
      </div>
    </details>
  );
}
