"use client";

import { useRef, useState } from "react";
import { Check, ChevronRight, CircleCheck, CircleX, LoaderCircle, X as XIcon } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { describeToolCall, type ToolCall } from "@/lib/describe";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useIsMobile } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";

function ToolStateIcon({ state }: { state?: ToolCall["state"] }) {
  if (state === "done") return <CircleCheck className="size-3.5 text-primary" />;
  if (state === "error") return <CircleX className="size-3.5 text-destructive" />;
  return <LoaderCircle className="size-3.5 text-muted-foreground animate-spin" />;
}

function PillStatusIcon({ loading, error }: { loading: number; error: number }) {
  if (error > 0) return <XIcon className="size-4 text-destructive flex-shrink-0" />;
  if (loading > 0) return <LoaderCircle className="size-4 text-muted-foreground animate-spin flex-shrink-0" />;
  return <Check className="size-4 text-green-500 flex-shrink-0" />;
}

function ToolCallItem({ call }: { call: ToolCall }) {
  return (
    <Collapsible className="group/call">
      <CollapsibleTrigger className="w-full flex items-center gap-2 py-1 text-xs text-muted-foreground hover:text-foreground cursor-pointer">
        <ChevronRight className="size-3 transition-transform group-data-[state=open]/call:rotate-90" />
        <ToolStateIcon state={call.state} />
        <span className="truncate">{describeToolCall(call.name, call.input)}</span>
        {call.output && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="ml-auto tabular-nums text-[11px]">
                {call.output.length.toLocaleString()} ch
              </span>
            </TooltipTrigger>
            <TooltipContent>
              State: {call.state ?? "loading"} · Output: {call.output.length.toLocaleString()} chars
            </TooltipContent>
          </Tooltip>
        )}
      </CollapsibleTrigger>
      <CollapsibleContent>
        {call.output ? (
          <pre className="ml-5 rounded-sm bg-background p-2 text-[11px] text-muted-foreground overflow-auto max-h-[200px] md:max-h-[260px] whitespace-pre-wrap">
            {call.output}
          </pre>
        ) : null}
      </CollapsibleContent>
    </Collapsible>
  );
}

export function StepGroup({
  icon: Icon,
  summary,
  calls,
}: {
  icon: React.ComponentType<{ className?: string }>;
  summary: string;
  calls: ToolCall[];
}) {
  const isMobile = useIsMobile();
  const loadingCount = calls.filter((call) => call.state === "loading" || !call.state).length;
  const errorCount = calls.filter((call) => call.state === "error").length;
  const doneCount = calls.filter((call) => call.state === "done").length;
  const manuallyToggled = useRef(false);
  const [forceOpen, setForceOpen] = useState(false);

  const defaultOpen = isMobile ? false : true;
  const isOpen = manuallyToggled.current ? forceOpen : defaultOpen;

  function handleToggle(nextOpen: boolean) {
    manuallyToggled.current = true;
    setForceOpen(nextOpen);
  }

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={handleToggle}
      className={cn(
        "group step-item rounded-lg md:rounded-sm",
        isMobile
          ? "bg-secondary/30 border border-border/30"
          : "border border-border bg-card",
      )}
    >
      <CollapsibleTrigger
        className={cn(
          "w-full flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors",
          isMobile ? "min-h-[44px] active:bg-secondary/60" : "hover:bg-accent",
        )}
      >
        {isMobile ? (
          <PillStatusIcon loading={loadingCount} error={errorCount} />
        ) : (
          <>
            <ChevronRight className="size-3.5 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
            <Icon className="size-3.5 text-primary" />
          </>
        )}
        <span className={cn(
          "truncate flex-1 min-w-0 text-left",
          isMobile ? "text-sm text-muted-foreground" : "text-sm text-foreground",
        )}>
          {summary}
        </span>
        {!isMobile && (
          errorCount > 0 ? (
            <CircleX className="ml-auto size-3.5 text-destructive" />
          ) : loadingCount > 0 ? (
            <LoaderCircle className="ml-auto size-3.5 text-muted-foreground animate-spin" />
          ) : (
            <CircleCheck className="ml-auto size-3.5 text-primary" />
          )
        )}
        <span className="text-[10px] font-mono text-muted-foreground tabular-nums flex-shrink-0">
          {doneCount}/{calls.length}
        </span>
        {isMobile && (
          <ChevronRight className={cn(
            "size-4 text-muted-foreground/50 transition-transform flex-shrink-0",
            isOpen && "rotate-90",
          )} />
        )}
      </CollapsibleTrigger>
      <CollapsibleContent className="px-3 pb-2 pl-4 md:pl-8 space-y-1">
        {calls.map((call) => (
          <ToolCallItem key={call.id} call={call} />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}
