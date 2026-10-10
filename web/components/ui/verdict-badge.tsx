import { VERDICT_COLOR, VERDICT_GLYPH, type Verdict } from "@/lib/verdict";

// Self-contained inline styles (not aero.css classes) so this renders
// identically in both the Aero-themed interactive replay page and the plain
// static export cards that get screenshotted into PNGs.
export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const color = VERDICT_COLOR[verdict.tier];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 10px",
        borderRadius: 999,
        background: `${color}1a`,
        color,
        fontSize: 13,
        fontWeight: 600,
        lineHeight: 1.4,
      }}
    >
      <span aria-hidden="true">{VERDICT_GLYPH[verdict.tier]}</span>
      {verdict.label}
    </span>
  );
}
