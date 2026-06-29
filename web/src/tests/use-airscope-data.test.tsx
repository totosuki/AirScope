import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAirScopeData } from "@/hooks/use-airscope-data";
import { getCurrentAircraft, getRecentTelemetry } from "@/lib/api/client";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    getCurrentAircraft: vi.fn(),
    getRecentTelemetry: vi.fn(),
  };
});

const currentResponse = {
  session_id: "demo-session",
  generated_at: "2026-06-29T01:00:01.000Z",
  aircraft: [],
};
const recentResponse = {
  session_id: "demo-session",
  generated_at: "2026-06-29T01:00:01.000Z",
  telemetry: [],
};

afterEach(() => vi.clearAllMocks());

describe("useAirScopeData", () => {
  it("loads both APIs and keeps previous data when a refresh fails", async () => {
    vi.mocked(getCurrentAircraft).mockResolvedValueOnce(currentResponse);
    vi.mocked(getRecentTelemetry).mockResolvedValueOnce(recentResponse);
    const { result } = renderHook(() => useAirScopeData("demo-session"));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.current).toEqual(currentResponse);
    expect(result.current.error).toBeNull();

    vi.mocked(getCurrentAircraft).mockRejectedValueOnce(new Error("network error"));
    vi.mocked(getRecentTelemetry).mockRejectedValueOnce(new Error("network error"));
    await act(async () => result.current.refresh());

    expect(result.current.current).toEqual(currentResponse);
    expect(result.current.error).toBe("network error");
    expect(result.current.failureCount).toBe(1);
  });
});
