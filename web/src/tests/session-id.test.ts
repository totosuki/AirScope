import { describe, expect, it } from "vitest";

import { resolveSessionId } from "@/lib/session-id";

describe("resolveSessionId", () => {
  it("uses the session_id query parameter when present", () => {
    expect(resolveSessionId(new URLSearchParams("session_id=live-rpi-20260713"), "demo-session"))
      .toBe("live-rpi-20260713");
  });

  it("trims the query parameter", () => {
    expect(resolveSessionId(new URLSearchParams("session_id=%20live-session%20"), "demo-session"))
      .toBe("live-session");
  });

  it("uses the fallback when the query parameter is missing or blank", () => {
    expect(resolveSessionId(new URLSearchParams(), "fallback-session")).toBe("fallback-session");
    expect(resolveSessionId(new URLSearchParams("session_id=%20"), "fallback-session"))
      .toBe("fallback-session");
  });
});
