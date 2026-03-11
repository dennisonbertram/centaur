/** GET /api/threads — list threads from Postgres */

import { getPool } from "@/lib/db";
import type { Harness, ThreadState } from "@/lib/types";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

function extractText(parts: unknown): string | null {
  const arr = Array.isArray(parts) ? parts : [];
  for (const p of arr) {
    if (p && typeof p === "object" && typeof p.text === "string") return p.text;
  }
  return null;
}

export async function GET() {
  try {
    const pool = getPool();
    const { rows } = await pool.query(`
      SELECT
        cm.thread_key,
        MIN(cm.created_at) AS created_at,
        MAX(cm.created_at) AS last_activity,
        COUNT(*)::int AS message_count,
        (SELECT parts FROM chat_messages cm2
         WHERE cm2.thread_key = cm.thread_key AND cm2.role = 'user'
         ORDER BY cm2.created_at ASC LIMIT 1) AS first_user_parts,
        (SELECT parts FROM chat_messages cm3
         WHERE cm3.thread_key = cm.thread_key AND cm3.role = 'user'
         ORDER BY cm3.created_at DESC LIMIT 1) AS last_user_parts,
        ss.thread_name,
        COALESCE(ss.harness, 'amp') AS harness,
        COALESCE(ss.state, 'stopped') AS state
      FROM chat_messages cm
      LEFT JOIN sandbox_sessions ss ON ss.thread_key = cm.thread_key
      GROUP BY cm.thread_key, ss.thread_name, ss.harness, ss.state
      ORDER BY MAX(cm.created_at) DESC
      LIMIT 200
    `);

    const threads = rows.map((row) => ({
      slack_thread_key: row.thread_key,
      harness: row.harness as Harness,
      state: row.state as ThreadState,
      created_at: new Date(row.created_at).getTime() / 1000,
      last_activity: new Date(row.last_activity).getTime() / 1000,
      turn_count: row.message_count,
      first_message: extractText(row.first_user_parts),
      last_user_message: extractText(row.last_user_parts),
      thread_name: row.thread_name,
    }));

    return Response.json({ threads }, {
      headers: { "Cache-Control": "public, s-maxage=3, stale-while-revalidate=1" },
    });
  } catch (err) {
    console.error("Failed to list threads:", err);
    return Response.json(
      { error: err instanceof Error ? err.message : "Database error" },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    );
  }
}
