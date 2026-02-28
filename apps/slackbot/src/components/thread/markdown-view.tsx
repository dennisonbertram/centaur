"use client";

import { Streamdown } from "streamdown";
import { code } from "@streamdown/code";

const plugins = { code };

export function MarkdownView({
  text,
  isStreaming,
}: {
  text: string;
  isStreaming?: boolean;
}) {
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
