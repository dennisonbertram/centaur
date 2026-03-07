/** GET /api/portfolio/positions -> POST /tools/paradigmdb/db_positions */

import { resilientFetch, API_URL, ApiError } from "@/lib/api-client";
import { decode } from "@toon-format/toon";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

/** Parse a tool result string that may be JSON or TOON-encoded. */
function parseResult(raw: unknown): unknown {
  if (typeof raw !== "string") return raw;
  // Try JSON first
  try {
    return JSON.parse(raw);
  } catch {
    // Fall back to TOON
  }
  try {
    const decoded = decode(raw, { strict: false });
    if (decoded !== undefined) return decoded;
  } catch {
    // ignore
  }
  return raw;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const fund = searchParams.get("fund") || undefined;
  const limit = parseInt(searchParams.get("limit") || "200", 10);

  try {
    const body: Record<string, unknown> = { limit };
    if (fund) body.fund = fund;

    const res = await resilientFetch(`${API_URL}/tools/paradigmdb/db_positions`, {
      method: "POST",
      body: JSON.stringify(body),
      signal: request.signal,
      timeoutMs: 15_000,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new ApiError(`Positions API error (${res.status}): ${text.slice(0, 300)}`, res.status, res.status >= 500);
    }

    const data = await res.json();
    // The result field may be TOON-encoded; decode it to plain JSON
    if (typeof data.result === "string") {
      data.result = parseResult(data.result);
    }
    return Response.json(data, { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    const status = err instanceof ApiError ? (err.status ?? 502) : 502;
    return Response.json(
      { error: err instanceof Error ? err.message : "API unreachable" },
      { status, headers: { "Cache-Control": "no-store" } },
    );
  }
}
