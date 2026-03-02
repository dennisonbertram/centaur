"use client";

import { useState } from "react";
import { Check, ChevronRight, CircleCheck, CircleX, Copy, SquareTerminal, Terminal, X as XIcon } from "lucide-react";

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
  const [copied, setCopied] = useState(false);

  async function copyCommand() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

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
            {ok ? <CircleCheck className="size-3.5 text-primary" /> : <CircleX className="size-3.5 text-destructive" />}
            <span className={ok ? "rounded bg-primary/10 px-1.5 py-0.5 text-primary" : "rounded bg-destructive/10 px-1.5 py-0.5 text-destructive"}>
              {exitCode}
            </span>
          </span>
        )}
        <ChevronRight className="size-4 text-muted-foreground/50 transition-transform group-open:rotate-90 flex-shrink-0 md:hidden" />
      </summary>
      <div className="border-t border-border/20 md:border-border px-3 py-2 space-y-2">
        <div className="relative">
          <pre className="hidden md:block rounded-sm bg-background p-2 pr-16 text-[11px] text-foreground overflow-auto overscroll-contain whitespace-pre-wrap">
            <SquareTerminal className="mr-1 inline size-3.5 text-muted-foreground" />$ {command}
          </pre>
          <button
            type="button"
            onClick={() => void copyCommand()}
            className="absolute right-2 top-2 hidden md:inline-flex items-center gap-1 rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
          >
            {copied ? <Check className="size-3 text-green-500" /> : <Copy className="size-3" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <pre className="rounded-sm bg-background p-2 text-[11px] text-foreground overflow-auto overscroll-contain whitespace-pre-wrap md:hidden">
          $ {command}
        </pre>
        {output && (
          <pre className="rounded-sm bg-background p-2 text-[11px] text-muted-foreground overflow-auto overscroll-contain max-h-[240px] md:max-h-[320px] whitespace-pre-wrap">
            {output}
          </pre>
        )}
      </div>
    </details>
  );
}
