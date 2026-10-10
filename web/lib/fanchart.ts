import type { SimPath } from "./types";

export interface WeeklyBand {
  week: number;
  p10: number;
  p50: number;
  p90: number;
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 1) return sorted[0];
  const idx = (sorted.length - 1) * p;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  const frac = idx - lo;
  return sorted[lo] + (sorted[hi] - sorted[lo]) * frac;
}

// Computes a p10/p50/p90 band per week from the full path set. The frozen
// SimResult contract ships full per-path balances, so we derive the band
// client-side rather than waiting on a server-side downsample (see
// 00-ARCHITECTURE.md Round 3 handshake, Dev A). If A ever ships a
// pre-downsampled `band` field, swap this out for a straight pass-through.
export function computeWeeklyBand(paths: SimPath[]): WeeklyBand[] {
  if (paths.length === 0) return [];
  const weeks = Math.max(...paths.map((p) => p.balances.length));
  const band: WeeklyBand[] = [];

  for (let w = 0; w < weeks; w++) {
    const values = paths
      .map((p) => p.balances[w])
      .filter((v): v is number => typeof v === "number")
      .sort((a, b) => a - b);
    if (values.length === 0) continue;
    band.push({
      week: w,
      p10: percentile(values, 0.1),
      p50: percentile(values, 0.5),
      p90: percentile(values, 0.9),
    });
  }

  return band;
}

// Picks an evenly spaced subset of paths to draw as thin individual lines
// on top of the band, so we never render all 500 polylines.
export function sampleRepresentativePaths(paths: SimPath[], count: number): SimPath[] {
  if (paths.length <= count) return paths;
  const step = paths.length / count;
  const sampled: SimPath[] = [];
  for (let i = 0; i < count; i++) {
    sampled.push(paths[Math.floor(i * step)]);
  }
  return sampled;
}
