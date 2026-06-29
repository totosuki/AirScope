"use client";

import {
  ArcElement,
  Chart as ChartJS,
  Legend,
  Tooltip as ChartTooltip,
} from "chart.js";
import { Doughnut } from "react-chartjs-2";

import { altitudeBandColor, getAltitudeBand } from "@/lib/aircraft";
import type { Aircraft } from "@/lib/api/types";

ChartJS.register(ArcElement, ChartTooltip, Legend);

export function AltitudeChart({ aircraft }: { aircraft: Aircraft[] }) {
  const counts = { ground: 0, low: 0, middle: 0, high: 0, unknown: 0 };
  aircraft.forEach((item) => counts[getAltitudeBand(item.altitude_ft)]++);

  return (
    <div className="mx-auto h-56 max-w-sm" role="img" aria-label="高度帯別の機体数グラフ">
      <Doughnut
        data={{
          labels: ["1,000ft未満", "1,000–9,999ft", "10,000–24,999ft", "25,000ft以上", "不明"],
          datasets: [{
            data: [counts.ground, counts.low, counts.middle, counts.high, counts.unknown],
            backgroundColor: [
              altitudeBandColor.ground,
              altitudeBandColor.low,
              altitudeBandColor.middle,
              altitudeBandColor.high,
              altitudeBandColor.unknown,
            ],
            borderWidth: 0,
          }],
        }}
        options={{
          maintainAspectRatio: false,
          plugins: { legend: { position: "bottom", labels: { boxWidth: 10, usePointStyle: true } } },
        }}
      />
    </div>
  );
}
