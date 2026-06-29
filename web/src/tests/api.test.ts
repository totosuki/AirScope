import { afterEach, describe, expect, it, vi } from "vitest";

import { getCurrentAircraft } from "@/lib/api/client";
import { parseCurrentAircraftResponse } from "@/lib/api/validation";

const aircraft = {
  icao24: "86D9A1",
  callsign: "ANA245",
  lat: 35.5523,
  lon: 139.7798,
  altitude_ft: 12800,
  ground_speed_kt: 286,
  track_deg: 72,
  vertical_rate_fpm: 640,
  squawk: "3301",
  seen_at: "2026-06-29T01:00:00.000Z",
  received_at: "2026-06-29T01:00:00.000Z",
  freshness_at: "2026-06-29T01:00:00.000Z",
  receiver_id: "airscope-demo-rpi",
  distance_km: 18.4,
  status: "current",
};

const response = {
  session_id: "demo-session",
  generated_at: "2026-06-29T01:00:01.000Z",
  aircraft: [aircraft],
};

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("current aircraft API", () => {
  it("accepts a valid response", () => {
    expect(parseCurrentAircraftResponse(response).aircraft[0].icao24).toBe("86D9A1");
  });

  it("rejects an invalid required field", () => {
    expect(() => parseCurrentAircraftResponse({ ...response, aircraft: [{ ...aircraft, lat: "35.5" }] }))
      .toThrow("航空機APIの応答形式が正しくありません");
  });

  it("builds the configured API URL without exposing a key", async () => {
    vi.stubEnv("NEXT_PUBLIC_AIRSCOPE_API_BASE_URL", "https://example.test/backend");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(response), { status: 200 }),
    );

    await getCurrentAircraft("demo-session");

    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/backend/api/aircraft/current?session_id=demo-session",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
    expect(fetchMock.mock.calls[0][0]).not.toContain("code=");
  });
});
