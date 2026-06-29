import type { CurrentAircraftResponse, RecentTelemetryResponse } from "./types";
import { parseCurrentAircraftResponse, parseRecentTelemetryResponse } from "./validation";

export const DEFAULT_API_BASE_URL = "http://localhost:7071";
export const DEFAULT_SESSION_ID = "demo-session";

function buildUrl(path: string, params: Record<string, string>): string {
  const baseUrl = process.env.NEXT_PUBLIC_AIRSCOPE_API_BASE_URL ??
    (typeof window === "undefined" ? DEFAULT_API_BASE_URL : window.location.origin);
  const url = new URL(path, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`);
  Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, value));
  return url.toString();
}

async function requestJson(url: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(url, { headers: { Accept: "application/json" }, signal });
  if (!response.ok) {
    throw new Error(`APIへの接続に失敗しました（HTTP ${response.status}）。`);
  }
  return response.json();
}

export async function getCurrentAircraft(
  sessionId: string,
  signal?: AbortSignal,
): Promise<CurrentAircraftResponse> {
  const value = await requestJson(
    buildUrl("api/aircraft/current", { session_id: sessionId }),
    signal,
  );
  return parseCurrentAircraftResponse(value);
}

export async function getRecentTelemetry(
  sessionId: string,
  limit = 50,
  signal?: AbortSignal,
): Promise<RecentTelemetryResponse> {
  const value = await requestJson(
    buildUrl("api/telemetry/recent", { session_id: sessionId, limit: String(limit) }),
    signal,
  );
  return parseRecentTelemetryResponse(value);
}
