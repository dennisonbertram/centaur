/** Proxy /api/threads/detail?key=... -> FastAPI /api/threads/detail?key=... */

import { apiGet, ApiError } from "@/lib/api-client";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const key = searchParams.get("key") || "";
  if (!key) {
    return Response.json({ error: "Missing thread key" }, { status: 400 });
  }

  try {
    const res = await apiGet("/api/threads/detail", { key }, { signal: request.signal });

    if (!res.ok) {
      const payload = await res.json().catch(() => null) as { error?: string; detail?: string } | null;
      const message =
        payload?.error ||
        payload?.detail ||
        (res.status === 404
          ? `Thread not found: ${key}`
          : `Failed to load thread (${res.status})`);
      return Response.json(
        { error: message },
        { status: res.status, headers: { "Cache-Control": "no-store" } }
      );
    }

    const data = await res.json();
    return Response.json(data, { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    const status = err instanceof ApiError ? (err.status ?? 502) : 502;
    return Response.json(
      { error: err instanceof Error ? err.message : "API unreachable" },
      { status, headers: { "Cache-Control": "no-store" } },
    );
  }
}
