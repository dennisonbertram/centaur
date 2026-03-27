import { CentaurClient } from "@centaur/api-client";

const API_URL = process.env.CENTAUR_API_URL || "http://api:8000";
const API_KEY = process.env.WEB_API_KEY || process.env.API_SECRET_KEY || "";

export const centaur = new CentaurClient({ apiUrl: API_URL, apiKey: API_KEY });
export const api = centaur.http;

export class ApiError extends Error {
  status?: number;
  details?: unknown;

  constructor(message: string, status?: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

type ResilientFetchOptions = RequestInit & {
  timeoutMs?: number;
  retries?: number;
  maxAttempts?: number;
  stream?: boolean;
};

export async function resilientFetch(url: string, opts: ResilientFetchOptions = {}): Promise<Response> {
  const {
    timeoutMs = 30_000,
    retries = 1,
    maxAttempts,
    stream = false,
    headers,
    ...init
  } = opts;

  const mergedHeaders = new Headers(headers || {});
  if (API_KEY && !mergedHeaders.has("Authorization")) {
    mergedHeaders.set("Authorization", `Bearer ${API_KEY}`);
  }
  if (init.body && !mergedHeaders.has("Content-Type")) {
    mergedHeaders.set("Content-Type", "application/json");
  }

  let lastErr: unknown;
  const attempts = Math.max(1, maxAttempts ?? retries + 1);

  for (let attempt = 0; attempt < attempts; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        ...init,
        headers: mergedHeaders,
        signal: controller.signal,
      });

      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new ApiError(
          `Request failed with status ${response.status}`,
          response.status,
          text.slice(0, 1000),
        );
      }

      if (!stream) {
        return response;
      }

      if (!response.body) {
        throw new ApiError("Stream response did not include a body", response.status);
      }
      return response;
    } catch (err) {
      lastErr = err;
      if (attempt === attempts - 1) {
        if (err instanceof ApiError) {
          throw err;
        }
        throw new ApiError(err instanceof Error ? err.message : "Request failed");
      }
    } finally {
      clearTimeout(timeout);
    }
  }

  throw new ApiError(lastErr instanceof Error ? lastErr.message : "Request failed");
}

export function apiGet(
  path: string,
  params?: Record<string, string | number | boolean | null | undefined>,
): Promise<Response> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value === null || value === undefined) continue;
    query.set(key, String(value));
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return resilientFetch(`${API_URL}${path}${suffix}`, { method: "GET" });
}

export { API_URL, API_KEY };
