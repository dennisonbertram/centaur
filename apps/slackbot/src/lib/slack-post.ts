const SLACK_BOT_TOKEN = process.env.SLACK_BOT_TOKEN || "";
const SLACK_RETRY_ATTEMPTS = 3;
const DEFAULT_SLACK_RETRY_MS = 1_000;
const MARKDOWN_TEXT_LIMIT = 11_800;

type SlackPostResponse = { ok: boolean; ts?: string; error?: string };

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function retryAfterMs(response: Response): number {
  const retryAfter = response.headers.get("Retry-After");
  const parsed = Number(retryAfter);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_SLACK_RETRY_MS;
  }
  return Math.max(DEFAULT_SLACK_RETRY_MS, Math.min(parsed * 1000, 30_000));
}

function splitMarkdown(markdown: string, maxChars: number = MARKDOWN_TEXT_LIMIT): string[] {
  const text = markdown.trim();
  if (!text) return [];
  if (text.length <= maxChars) return [text];

  const chunks: string[] = [];
  let current = "";

  const flushCurrent = (): void => {
    const cleaned = current.trim();
    if (cleaned) chunks.push(cleaned);
    current = "";
  };

  const paragraphs = text.split(/\n{2,}/);
  for (const rawParagraph of paragraphs) {
    const paragraph = rawParagraph.trim();
    if (!paragraph) continue;

    const candidate = current ? `${current}\n\n${paragraph}` : paragraph;
    if (candidate.length <= maxChars) {
      current = candidate;
      continue;
    }

    if (current) flushCurrent();
    if (paragraph.length <= maxChars) {
      current = paragraph;
      continue;
    }

    const lines = paragraph.split("\n");
    for (const rawLine of lines) {
      const line = rawLine.trimEnd();
      const lineCandidate = current ? `${current}\n${line}` : line;
      if (lineCandidate.length <= maxChars) {
        current = lineCandidate;
        continue;
      }

      if (current) flushCurrent();
      if (line.length <= maxChars) {
        current = line;
        continue;
      }

      let remaining = line;
      while (remaining.length > maxChars) {
        let splitAt = remaining.lastIndexOf(" ", maxChars);
        if (splitAt < Math.floor(maxChars * 0.6)) {
          splitAt = maxChars;
        }
        chunks.push(remaining.slice(0, splitAt).trimEnd());
        remaining = remaining.slice(splitAt).trimStart();
      }
      current = remaining;
    }
  }

  if (current) flushCurrent();
  return chunks;
}

export async function postSlackMessage(payload: Record<string, unknown>): Promise<SlackPostResponse> {
  if (!SLACK_BOT_TOKEN) {
    throw new Error("SLACK_BOT_TOKEN not configured");
  }

  for (let attempt = 0; attempt < SLACK_RETRY_ATTEMPTS; attempt += 1) {
    const res = await fetch("https://slack.com/api/chat.postMessage", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${SLACK_BOT_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (res.status === 429 && attempt + 1 < SLACK_RETRY_ATTEMPTS) {
      await sleep(retryAfterMs(res));
      continue;
    }
    if (!res.ok) {
      throw new Error(`chat.postMessage failed (${res.status})`);
    }

    const data = (await res.json()) as SlackPostResponse;
    if (data.ok) {
      return data;
    }
    if (data.error === "ratelimited" && attempt + 1 < SLACK_RETRY_ATTEMPTS) {
      await sleep(retryAfterMs(res));
      continue;
    }
    throw new Error(`chat.postMessage failed: ${data.error ?? "unknown_error"}`);
  }

  throw new Error(`chat.postMessage failed after ${SLACK_RETRY_ATTEMPTS} attempts`);
}

export async function postMarkdownToSlack(
  channel: string,
  markdown: string,
  threadTs?: string
): Promise<SlackPostResponse | null> {
  const chunks = splitMarkdown(markdown);
  if (chunks.length === 0) return null;

  let rootTs = threadTs;
  let firstResponse: SlackPostResponse | null = null;
  for (let index = 0; index < chunks.length; index += 1) {
    const response = await postSlackMessage({
      channel,
      ...(rootTs ? { thread_ts: rootTs } : {}),
      markdown_text: chunks[index],
      unfurl_links: false,
    });
    if (!firstResponse) firstResponse = response;
    if (!rootTs && response.ts) {
      rootTs = response.ts;
    }
  }

  return firstResponse;
}
