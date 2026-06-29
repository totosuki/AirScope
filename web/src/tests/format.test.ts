import { describe, expect, it } from "vitest";

import { getAltitudeBand } from "@/lib/aircraft";
import { formatDateTime, formatRelativeTime } from "@/lib/format";

describe("dashboard formatting", () => {
  it("formats UTC timestamps in Japan time", () => {
    expect(formatDateTime("2026-06-29T01:00:00.000Z")).toContain("10:00:00");
  });

  it("formats elapsed time", () => {
    expect(formatRelativeTime("2026-06-29T01:00:00.000Z", Date.parse("2026-06-29T01:03:10.000Z")))
      .toBe("3分前");
  });

  it("classifies altitude bands", () => {
    expect(getAltitudeBand(null)).toBe("unknown");
    expect(getAltitudeBand(999)).toBe("ground");
    expect(getAltitudeBand(12_800)).toBe("middle");
    expect(getAltitudeBand(30_000)).toBe("high");
  });
});
