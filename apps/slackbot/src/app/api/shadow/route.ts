/** POST /api/shadow — backtest historical #ai-agent messages through v2.
 *
 * Body (JSON):
 *   limit:  number of messages to replay (default 10, max 50)
 *   before: Slack timestamp — only replay messages older than this
 *
 * Requires Authorization: Bearer <API_KEY>
 */

import { backtest } from "@/lib/shadow";

const API_KEY = process.env.AI_V2_API_KEY || "";

export async function POST(request: Request) {
  // Auth check
  const auth = request.headers.get("authorization") || "";
  if (!API_KEY || !auth.startsWith("Bearer ") || auth.slice(7) !== API_KEY) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json().catch(() => ({}));
  const limit = Math.min(Math.max(Number(body.limit) || 10, 1), 50);
  const before = body.before as string | undefined;

  const result = await backtest(limit, before);
  return Response.json(result);
}
