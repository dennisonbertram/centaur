/** GET /api/messages?key={thread_key} — load messages from Postgres */

import { NextRequest } from "next/server";
import { safeValidateUIMessages } from "ai";
import { dataPartSchemas } from "@/lib/data-part-schemas";
import { getPool } from "@/lib/db";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

export async function GET(request: NextRequest) {
  const threadKey = request.nextUrl.searchParams.get("key");
  if (!threadKey) {
    return Response.json({ error: "Missing key parameter" }, { status: 400 });
  }

  try {
    const pool = getPool();
    const { rows } = await pool.query(
      "SELECT id, role, parts, created_at, metadata FROM chat_messages WHERE thread_key = $1 ORDER BY created_at",
      [threadKey],
    );

    const messages = rows.map((row) => ({
      id: row.id,
      role: row.role,
      parts: row.parts,
      createdAt: row.created_at ? new Date(row.created_at).toISOString() : null,
      metadata: row.metadata,
    }));

    const validated = await safeValidateUIMessages({
      messages,
      dataSchemas: dataPartSchemas,
    });

    return Response.json(
      validated.success ? validated.data : messages,
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (err) {
    console.error("Failed to fetch messages:", err);
    return Response.json(
      { error: err instanceof Error ? err.message : "Database error" },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
