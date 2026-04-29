/**
 * Next.js instrumentation hook — runs once at server startup.
 *
 * Eagerly initializes the Bolt-backed Slack app so the adapter is ready
 * before any webhooks arrive. Without this, the first webhook after
 * a deploy can hit the slackbot before the app is initialized,
 * returning 404/503 and losing the message.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { ensureBotReady } = await import("@/lib/bot/setup");
    await ensureBotReady();
  }
}
