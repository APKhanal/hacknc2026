import { computeWeeklyBand, sampleRepresentativePaths } from "@/lib/fanchart";
import { classifyBreachRate } from "@/lib/verdict";
import { VerdictBadge } from "@/components/ui/verdict-badge";
import { culpritMatters, dipSentence, horizonLabel, money, oddsStat, verdictSentence, weekLabel } from "@/lib/summary";
import type { RunInputs, SimResult } from "@/lib/types";

const usd0 = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

const cardStyle: React.CSSProperties = {
  width: 680,
  background: "var(--surface)",
  border: "1px solid #d9eaf4",
  borderRadius: 14,
  boxShadow: "0 5px 16px #4795b022",
  padding: 28,
  boxSizing: "border-box",
  fontFamily: '"Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif',
  color: "var(--ink)",
};

/**
 * Graph only - no slider, no percentile table, no "Inspect week" control.
 * Those are interactive affordances that make no sense in a static PNG; this
 * reuses the same computeWeeklyBand/sampleRepresentativePaths + mark specs as
 * the interactive BalanceChart (replay-result.tsx) for visual consistency,
 * just without the parts that only make sense live in a browser.
 */
export function GraphCard({ result }: { result: SimResult }) {
  const band = computeWeeklyBand(result.paths);
  const samples = sampleRepresentativePaths(result.paths, 20);
  // Only worth overlaying when a decision was actually applied - with no
  // delta, baseline_band is identical to the decision band already drawn.
  const showBaseline = result.delta_breach_rate !== null && result.baseline_band.length > 0;
  let min = result.breach_threshold, max = result.breach_threshold;
  for (const path of result.paths) for (const value of path.balances) { min = Math.min(min, value); max = Math.max(max, value); }
  if (showBaseline) for (const b of result.baseline_band) { min = Math.min(min, b.p10); max = Math.max(max, b.p90); }
  const pad = Math.max((max - min) * 0.05, 1);
  min -= pad; max += pad;
  const x = (w: number) => 68 + (w / Math.max(result.horizon_weeks, 1)) * 552;
  const y = (v: number) => 220 - ((v - min) / Math.max(max - min, 1)) * 190;
  const upper = band.map(p => `${x(p.week)},${y(p.p90)}`).join(" L ");
  const lower = [...band].reverse().map(p => `${x(p.week)},${y(p.p10)}`).join(" L ");
  const median = band.map(p => `${x(p.week)},${y(p.p50)}`).join(" L ");
  const baseUpper = result.baseline_band.map(p => `${x(p.week)},${y(p.p90)}`).join(" L ");
  const baseLower = [...result.baseline_band].reverse().map(p => `${x(p.week)},${y(p.p10)}`).join(" L ");
  const baseMedian = result.baseline_band.map(p => `${x(p.week)},${y(p.p50)}`).join(" L ");

  return (
    <div data-graph-card="true" style={cardStyle}>
      <h2 style={{ margin: "0 0 4px", fontSize: 17, fontWeight: 600, color: "var(--ink)" }}>How your balance could change</h2>
      <p style={{ margin: "0 0 14px", fontSize: 13, color: "var(--muted)" }}>
        Next {horizonLabel(result.horizon_weeks)} &middot; dark line is your typical balance &middot; shaded area is where most simulations landed &middot; dashed line is {usd0(result.breach_threshold)}
      </p>
      <svg viewBox="0 0 640 250" width="100%" height="auto" role="img"
           aria-label={`${result.n_paths} simulated balance paths across ${result.horizon_weeks} weeks${showBaseline ? ", with a baseline comparison" : ""}`}>
        {[min, (min + max) / 2, max].map(value => (
          <g key={value}>
            <line className="chart-grid" x1={68} x2={620} y1={y(value)} y2={y(value)} />
            <text className="chart-label" x={62} y={y(value)} textAnchor="end" dominantBaseline="middle">
              {usd0(value)}
            </text>
          </g>
        ))}
        {showBaseline && <path className="chart-baseline-band" d={`M ${baseUpper} L ${baseLower} Z`} />}
        <path className="chart-band" d={`M ${upper} L ${lower} Z`} />
        {samples.map(p => (
          <path key={p.path_id} className="chart-sample" d={`M ${p.balances.map((v, w) => `${x(w)},${y(v)}`).join(" L ")}`} />
        ))}
        {showBaseline && <path className="chart-baseline-median" d={`M ${baseMedian}`} />}
        <path className="chart-median" d={`M ${median}`} />
        <line className="chart-threshold" x1={68} x2={620} y1={y(result.breach_threshold)} y2={y(result.breach_threshold)} />
        {[0, Math.round(result.horizon_weeks / 2), result.horizon_weeks].map(w => (
          <text key={w} className="chart-label" x={x(w)} y={242}
                textAnchor={w === 0 ? "start" : w === result.horizon_weeks ? "end" : "middle"}>
            {weekLabel(w)}
          </text>
        ))}
      </svg>
      {showBaseline && (
        <div className="chart-legend">
          <span><span className="chart-legend-swatch" style={{ background: "#13294b" }} />With this purchase</span>
          <span><span className="chart-legend-swatch" style={{ background: "#eb6834" }} />Without it</span>
        </div>
      )}
    </div>
  );
}

/** Clean dashboard stat card - the headline numbers, no interactive chrome. */
export function StatsCard({ result, inputs = null }: { result: SimResult; inputs?: RunInputs | null }) {
  const rate = result.delta_breach_rate ?? result.baseline_breach_rate;
  const asked = inputs?.created_at ? new Date(inputs.created_at) : null;
  const dip = dipSentence(result, asked);
  const stat = (label: string, value: string, badge?: React.ReactNode) => (
    <div>
      <div style={{ fontSize: 12, color: "var(--muted)" }}>{label}</div>
      <div style={{ fontSize: 30, fontWeight: 500, marginTop: 6, fontVariantNumeric: "tabular-nums" }}>{value}</div>
      {badge && <div style={{ marginTop: 8 }}>{badge}</div>}
    </div>
  );

  return (
    <div data-stats-card="true" style={cardStyle}>
      <h2 style={{ margin: "0 0 6px", fontSize: 19, fontWeight: 600, color: "var(--ink)", lineHeight: 1.35 }}>
        {verdictSentence(result, inputs?.decision ?? inputs?.delta ?? null, asked)}
      </h2>
      {dip && <p style={{ margin: "0 0 18px", fontSize: 14, color: "var(--ink)", lineHeight: 1.5 }}>{dip}</p>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20, margin: "18px 0 14px" }}>
        {stat(result.delta_breach_rate === null ? "Chance of dipping below $0" : "With this purchase", oddsStat(rate), <VerdictBadge verdict={classifyBreachRate(rate)} />)}
        {result.delta_breach_rate !== null && stat("Without it", oddsStat(result.baseline_breach_rate))}
        {stat("Typical lowest balance", usd0(result.median_min_balance))}
      </div>
      <p style={{ margin: 0, fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
        Chance your balance dips below {usd0(result.breach_threshold)} at least once in the next {horizonLabel(result.horizon_weeks)}, from {result.n_paths} simulations.
      </p>
      {culpritMatters(result.culprit) && (
        <div style={{ borderTop: "1px solid #e4eef4", paddingTop: 16, marginTop: 18 }}>
          <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Biggest recurring cost</div>
          <div style={{ fontSize: 17, fontWeight: 600 }}>{result.culprit.label} &middot; {money(result.culprit.amount)} per payment</div>
          <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
            Without it, your chance of dipping below {usd0(result.breach_threshold)} would be {Math.round(result.culprit.marginal_contribution * 100)} points lower.
          </div>
        </div>
      )}
    </div>
  );
}
