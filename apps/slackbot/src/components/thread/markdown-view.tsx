"use client";

import { lazy, Suspense, useMemo } from "react";
import { Streamdown } from "streamdown";
import { code } from "@streamdown/code";
import { extractDashboardBlocks } from "@/lib/dashboard-parser";

const DashboardLayout = lazy(() =>
  import("@/components/dashboard/layout").then((m) => ({ default: m.DashboardLayout })),
);

const plugins = { code };

export function MarkdownView({
  text,
  isStreaming,
}: {
  text: string;
  isStreaming?: boolean;
}) {
  const dashboardBlocks = useMemo(
    () => (isStreaming ? [] : extractDashboardBlocks(text)),
    [text, isStreaming],
  );

  if (dashboardBlocks.length === 0) {
    return (
      <div className="prose-console">
        <Streamdown
          plugins={plugins}
          shikiTheme={["github-dark", "github-dark"]}
          animated={{ animation: "fadeIn", duration: 120, sep: "word" }}
          isAnimating={!!isStreaming}
          caret={isStreaming ? "block" : undefined}
        >
          {text}
        </Streamdown>
      </div>
    );
  }

  return (
    <div className="prose-console space-y-4">
      {dashboardBlocks.map((block, i) => (
        <div key={i}>
          {block.before.trim() && (
            <Streamdown
              plugins={plugins}
              shikiTheme={["github-dark", "github-dark"]}
            >
              {block.before}
            </Streamdown>
          )}
          <Suspense
            fallback={
              <div className="h-32 rounded-lg border border-border bg-card animate-pulse" />
            }
          >
            <DashboardLayout spec={block.spec} />
          </Suspense>
          {block.after.trim() && (
            <Streamdown
              plugins={plugins}
              shikiTheme={["github-dark", "github-dark"]}
            >
              {block.after}
            </Streamdown>
          )}
        </div>
      ))}
    </div>
  );
}
