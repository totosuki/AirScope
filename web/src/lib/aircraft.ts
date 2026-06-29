export type AltitudeBand = "ground" | "low" | "middle" | "high" | "unknown";

export function getAltitudeBand(altitude: number | null): AltitudeBand {
  if (altitude === null) return "unknown";
  if (altitude < 1000) return "ground";
  if (altitude < 10000) return "low";
  if (altitude < 25000) return "middle";
  return "high";
}

export const altitudeBandColor: Record<AltitudeBand, string> = {
  ground: "#22c55e",
  low: "#06b6d4",
  middle: "#f59e0b",
  high: "#ef4444",
  unknown: "#94a3b8",
};
