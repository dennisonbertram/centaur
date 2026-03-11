/** /api/threads/detail?key=... — thread detail from Postgres */

import { getPool } from "@/lib/db";
import type { Harness, Participant, ThreadDetail, ThreadState } from "@/lib/types";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

function extractText(parts: unknown): string | null {
  const arr = Array.isArray(parts) ? parts : [];
  for (const p of arr) {
    if (p && typeof p === "object" && typeof p.text === "string") return p.text;
  }
  return null;
}

function coerceNonNegativeInt(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
    return Math.trunc(value);
  }
  return 0;
}

function parseTokenUsage(value: unknown): ThreadDetail["token_usage"] {
  if (!value || typeof value !== "object") return null;
  const payload = value as Record<string, unknown>;
  const inputTokens =
    typeof payload.input_tokens === "number" && Number.isFinite(payload.input_tokens)
      ? coerceNonNegativeInt(payload.input_tokens)
      : null;
  const outputTokens =
    typeof payload.output_tokens === "number" && Number.isFinite(payload.output_tokens)
      ? coerceNonNegativeInt(payload.output_tokens)
      : null;
  const totalTokens =
    coerceNonNegativeInt(payload.total_tokens) ||
    coerceNonNegativeInt(inputTokens) + coerceNonNegativeInt(outputTokens);
  if (totalTokens <= 0) return null;
  const models = Array.isArray(payload.models)
    ? payload.models.filter((model): model is string => typeof model === "string" && model.trim().length > 0)
    : [];
  return {
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    total_tokens: totalTokens,
    cost_usd:
      typeof payload.cost_usd === "number" && Number.isFinite(payload.cost_usd)
        ? payload.cost_usd
        : null,
    quality: payload.quality === "authoritative" ? "authoritative" : "estimated",
    breakdown:
      payload.breakdown === "known" || inputTokens !== null || outputTokens !== null
        ? "known"
        : "unknown",
    models,
  } as ThreadDetail["token_usage"];
}

function preferTokenUsageSnapshot(
  previous: ThreadDetail["token_usage"],
  incoming: ThreadDetail["token_usage"],
): ThreadDetail["token_usage"] {
  if (!previous) return incoming;
  if (!incoming) return previous;
  if (incoming.total_tokens > previous.total_tokens) return incoming;
  if (incoming.total_tokens < previous.total_tokens) return previous;
  return {
    total_tokens: previous.total_tokens,
    input_tokens: incoming.input_tokens ?? previous.input_tokens ?? null,
    output_tokens: incoming.output_tokens ?? previous.output_tokens ?? null,
    cost_usd: incoming.cost_usd ?? previous.cost_usd ?? null,
    quality:
      previous.quality === "authoritative" || incoming.quality === "authoritative"
        ? "authoritative"
        : "estimated",
    breakdown:
      previous.breakdown === "known" || incoming.breakdown === "known" ? "known" : "unknown",
    models: Array.from(new Set([...(previous.models ?? []), ...(incoming.models ?? [])])).sort(),
  };
}

function aggregateTokenUsage(
  total: ThreadDetail["token_usage"],
  incoming: ThreadDetail["token_usage"],
): ThreadDetail["token_usage"] {
  if (!total) return incoming;
  if (!incoming) return total;

  const inputTokens =
    total.input_tokens !== null && incoming.input_tokens !== null
      ? total.input_tokens + incoming.input_tokens
      : null;
  const outputTokens =
    total.output_tokens !== null && incoming.output_tokens !== null
      ? total.output_tokens + incoming.output_tokens
      : null;
  const knownCost =
    total.cost_usd !== null || incoming.cost_usd !== null
      ? (total.cost_usd ?? 0) + (incoming.cost_usd ?? 0)
      : null;

  return {
    total_tokens: total.total_tokens + incoming.total_tokens,
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    cost_usd: knownCost,
    quality:
      total.quality === "authoritative" && incoming.quality === "authoritative"
        ? "authoritative"
        : "estimated",
    breakdown: inputTokens !== null || outputTokens !== null ? "known" : "unknown",
    models: Array.from(new Set([...(total.models ?? []), ...(incoming.models ?? [])])).sort(),
  };
}

function fallbackParticipantName(userId: string): string {
  return /^U[A-Z0-9]+$/.test(userId) ? `User ${userId.slice(-4)}` : userId;
}

function collectParticipant(
  map: Map<string, Participant>,
  userId: string,
  payload?: Record<string, unknown>,
) {
  const existing = map.get(userId);
  const name =
    typeof payload?.user_name === "string" && payload.user_name.trim()
      ? payload.user_name.trim()
      : typeof payload?.name === "string" && payload.name.trim()
        ? payload.name.trim()
        : existing?.name || fallbackParticipantName(userId);
  const username =
    typeof payload?.username === "string" && payload.username.trim()
      ? payload.username.trim()
      : existing?.username ?? null;
  const avatarUrl =
    typeof payload?.avatar_url === "string" && payload.avatar_url.trim()
      ? payload.avatar_url.trim()
      : existing?.avatar_url ?? null;

  map.set(userId, {
    id: userId,
    name,
    username,
    avatar_url: avatarUrl,
  });
}

function extractParticipantsFromRows(
  rows: Array<{ parts: unknown; metadata: unknown }>,
): Participant[] {
  const participants = new Map<string, Participant>();
  for (const row of rows) {
    const metadata = row.metadata && typeof row.metadata === "object"
      ? (row.metadata as Record<string, unknown>)
      : null;
    const metadataUserId =
      typeof metadata?.user_id === "string" && metadata.user_id.trim()
        ? metadata.user_id.trim()
        : null;
    if (metadataUserId) {
      collectParticipant(participants, metadataUserId, metadata ?? undefined);
    }

    if (!Array.isArray(row.parts)) continue;
    for (const part of row.parts) {
      if (!part || typeof part !== "object") continue;
      const record = part as Record<string, unknown>;
      const type = typeof record.type === "string" ? record.type : "";
      if (type !== "data-user-message" && type !== "data-context-message") continue;
      const data =
        record.data && typeof record.data === "object"
          ? (record.data as Record<string, unknown>)
          : null;
      const userId =
        typeof data?.user_id === "string" && data.user_id.trim()
          ? data.user_id.trim()
          : null;
      if (!userId) continue;
      collectParticipant(participants, userId, data ?? undefined);
    }
  }
  return Array.from(participants.values());
}

function extractTokenUsageFromRows(
  rows: Array<{ parts: unknown; metadata: unknown }>,
): ThreadDetail["token_usage"] {
  let usage: ThreadDetail["token_usage"] = null;
  for (const row of rows) {
    let rowUsage: ThreadDetail["token_usage"] = null;
    const metadata =
      row.metadata && typeof row.metadata === "object"
        ? (row.metadata as Record<string, unknown>)
        : null;
    if (metadata?.token_usage) {
      rowUsage = preferTokenUsageSnapshot(rowUsage, parseTokenUsage(metadata.token_usage));
    }
    if (Array.isArray(row.parts)) {
      for (const part of row.parts) {
        if (!part || typeof part !== "object") continue;
        const record = part as Record<string, unknown>;
        if (record.type !== "data-token-usage") continue;
        rowUsage = preferTokenUsageSnapshot(rowUsage, parseTokenUsage(record.data));
      }
    }
    usage = aggregateTokenUsage(usage, rowUsage);
  }
  return usage;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const key = searchParams.get("key") || "";
  if (!key) {
    return Response.json({ error: "Missing thread key" }, { status: 400 });
  }

  try {
    const pool = getPool();
    const { rows } = await pool.query(
        `SELECT
          MIN(cm.created_at) AS created_at,
          MAX(cm.created_at) AS last_activity,
          COUNT(*)::int AS message_count,
          (SELECT parts FROM chat_messages cm2
           WHERE cm2.thread_key = $1 AND cm2.role = 'user'
           ORDER BY cm2.created_at DESC LIMIT 1
          ) AS last_user_parts,
          ss.thread_name,
          COALESCE(ss.harness, 'amp') AS harness,
          COALESCE(ss.state, 'stopped') AS state
        FROM chat_messages cm
        LEFT JOIN sandbox_sessions ss ON ss.thread_key = cm.thread_key
        WHERE cm.thread_key = $1
        GROUP BY ss.thread_name, ss.harness, ss.state`,
        [key],
      );

    const row = rows[0];
    if (!row || !row.created_at) {
      return Response.json(
        { error: `Thread not found: ${key}` },
        { status: 404, headers: { "Cache-Control": "no-store" } },
      );
    }

    const detail: ThreadDetail = {
      slack_thread_key: key,
      harness: row.harness as Harness,
      state: row.state as ThreadState,
      created_at: new Date(row.created_at).getTime() / 1000,
      last_activity: new Date(row.last_activity).getTime() / 1000,
      message_count: row.message_count,
      last_user_message: extractText(row.last_user_parts),
      token_usage: null,
      thread_name: row.thread_name,
    };

    const participantRows = await pool.query<{ parts: unknown; metadata: unknown }>(
      `SELECT parts, metadata
       FROM chat_messages
       WHERE thread_key = $1
       ORDER BY created_at DESC
       LIMIT 200`,
      [key],
    );
    detail.participants = extractParticipantsFromRows(participantRows.rows);
    detail.token_usage = extractTokenUsageFromRows(participantRows.rows);

    return Response.json(detail, {
      headers: { "Cache-Control": "public, s-maxage=5, stale-while-revalidate=3" },
    });
  } catch (err) {
    return Response.json(
      { error: err instanceof Error ? err.message : "Database error" },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    );
  }
}
