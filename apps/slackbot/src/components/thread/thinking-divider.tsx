"use client";

import { Brain, ChevronRight } from "lucide-react";

export function ThinkingDivider({ text, durationS }: { text: string; durationS?: number }) {
  if (!text.trim()) return null;
  const label = durationS ? `Thought for ${durationS}s` : "Thinking\u2026";
  return (
    <details className="group step-item rounded-lg md:rounded-none bg-secondary/30 md:bg-transparent border border-border/30 md:border-0">
      <summary className="list-none cursor-pointer select-none flex items-center gap-2 min-h-[44px] md:min-h-0 px-3 md:px-0 py-2 md:py-0 text-xs text-muted-foreground active:bg-secondary/60 md:active:bg-transparent [&::-webkit-details-marker]:hidden">
        <Brain className="size-4 md:size-3 text-purple-400 flex-shrink-0" />
        <span className="flex-1 text-sm md:text-xs">{label}</span>
        <ChevronRight className="size-4 md:size-3 text-muted-foreground/50 transition-transform group-open:rotate-90 flex-shrink-0" />
      </summary>
      <pre className="mt-1 mx-3 md:mx-0 mb-2 md:mb-0 rounded-sm bg-background p-3 max-h-[180px] md:max-h-[220px] overflow-auto whitespace-pre-wrap font-mono text-xs italic text-muted-foreground">
        {text}
      </pre>
    </details>
  );
}
