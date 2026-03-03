"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { MessageSquarePlus } from "lucide-react";
import { toast } from "sonner";
import { MessageInput } from "@/components/thread/message-input";
import { MobileTabBar } from "@/components/thread/mobile-tab-bar";

export default function NewSessionPage() {
  const router = useRouter();
  const [sending, setSending] = useState(false);

  const handleSend = useCallback(
    async (message: string) => {
      const text = message.trim();
      if (!text || sending) return;
      setSending(true);

      const threadKey = `ui:${crypto.randomUUID()}`;
      const encoded = encodeURIComponent(threadKey);

      try {
        const res = await fetch("/api/agent/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            slack_thread_key: threadKey,
            message: text,
            source: "thread_ui",
          }),
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.error ?? `Failed (${res.status})`);
        }

        router.push(`/${encoded}`);
      } catch (err) {
        toast(err instanceof Error ? err.message : "Failed to start session");
        setSending(false);
      }
    },
    [router, sending],
  );

  return (
    <div className="h-dvh md:h-full flex flex-col bg-background overflow-hidden">
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="text-center max-w-md">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-xl border border-border/80 bg-card/60">
            <MessageSquarePlus className="size-6 text-muted-foreground" />
          </div>
          <h1 className="text-lg font-semibold text-foreground">New Session</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Start a conversation with the AI agent. Your session will appear in the sidebar.
          </p>
        </div>
      </div>

      <MessageInput
        mode={sending ? "running" : "idle"}
        onSend={handleSend}
      />

      <MobileTabBar activeThreadHref="/" hasRunningAgent={false} hasError={false} />
    </div>
  );
}
