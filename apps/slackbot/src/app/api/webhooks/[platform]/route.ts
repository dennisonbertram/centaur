import { after } from "next/server";
import { getBot } from "@/lib/bot";
import { maybeShadow } from "@/lib/shadow";

export async function POST(
  request: Request,
  context: { params: Promise<{ platform: string }> }
) {
  const bot = getBot();
  const { platform } = await context.params;

  type Platform = keyof typeof bot.webhooks;
  const handler = bot.webhooks[platform as Platform];
  if (!handler) {
    return new Response(`Unknown platform: ${platform}`, { status: 404 });
  }

  // Clone body before the Chat SDK consumes it so we can check for shadows
  if (platform === "slack") {
    const cloned = request.clone();
    after(async () => {
      try {
        const body = await cloned.json();
        await maybeShadow(body);
      } catch {
        /* ignore parse errors */
      }
    });
  }

  return handler(request, {
    waitUntil: (task) => after(() => task),
  });
}
