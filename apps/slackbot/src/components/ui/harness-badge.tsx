import type { Harness } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { harnessIconFor } from "@/components/icons/harness-icons";

interface HarnessBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  harness: Harness | string;
}

const HARNESS_STYLES: Record<string, string> = {
  amp: "bg-muted/80 text-foreground/85",
  "claude-code": "bg-muted text-muted-foreground",
  codex: "bg-primary/12 text-primary",
  "pi-mono": "bg-muted/70 text-foreground/80",
  eng: "bg-primary/10 text-primary",
  engineer: "bg-primary/10 text-primary",
};

export function HarnessBadge({ harness, className, ...props }: HarnessBadgeProps) {
  const Icon = harnessIconFor(harness);
  return (
    <Badge
      className={cn(
        "inline-flex items-center gap-1 rounded-[6px] text-xs font-semibold uppercase tracking-wider",
        HARNESS_STYLES[harness] ?? "bg-secondary text-muted-foreground",
        className,
      )}
      {...props}
    >
      <Icon className="size-3 shrink-0" />
      {harness}
    </Badge>
  );
}
