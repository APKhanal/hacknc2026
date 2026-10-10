// Shared between the interactive replay page (replay-result.tsx) and the
// static stats card (export-cards.tsx), so the phone reply and the
// big-screen replay always agree. Thresholds match llm/render.py's
// fake_gemini_render on the Python side - keep both in sync if either changes.

export type VerdictTier = "good" | "warning" | "critical";

export interface Verdict {
  tier: VerdictTier;
  label: string;
}

export function classifyBreachRate(rate: number): Verdict {
  if (rate < 0.2) return { tier: "good", label: "Sustainable" };
  if (rate < 0.5) return { tier: "warning", label: "Worth a look" };
  return { tier: "critical", label: "Real stretch" };
}

// Dataviz skill's validated status palette (fixed, never themed).
export const VERDICT_COLOR: Record<VerdictTier, string> = {
  good: "#0ca30c",
  warning: "#fab219",
  critical: "#d03b3b",
};

// Distinct shapes per tier, not just color/text - a status color never
// carries meaning alone (icon + label + shape).
export const VERDICT_GLYPH: Record<VerdictTier, string> = {
  good: "●", // ●
  warning: "▲", // ▲
  critical: "■", // ■
};
