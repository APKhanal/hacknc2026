import { computeWeeklyBand, sampleRepresentativePaths } from "@/lib/fanchart";
import type { SimResult } from "@/lib/types";

const usd0 = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
const usd2 = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
const percent = (n: number) => new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 }).format(n);
const points = (n: number) => `${(n * 100).toFixed(1)} pts`;

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
  let min = result.breach_threshold, max = result.breach_threshold;
  for (const path of result.paths) for (const value of path.balances) { min = Math.min(min, value); max = Math.max(max, value); }
  const pad = Math.max((max - min) * 0.05, 1);
  min -= pad; max += pad;
  const x = (w: number) => 68 + (w / Math.max(result.horizon_weeks, 1)) * 552;
  const y = (v: number) => 220 - ((v - min) / Math.max(max - min, 1)) * 190;
  const upper = band.map(p => `${x(p.week)},${y(p.p90)}`).join(" L ");
  const lower = [...band].reverse().map(p => `${x(p.week)},${y(p.p10)}`).join(" L ");
  const median = band.map(p => `${x(p.week)},${y(p.p50)}`).join(" L ");

  return (
    <div data-graph-card="true" style={cardStyle}>
      <h2 style={{ margin: "0 0 4px", fontSize: 17, fontWeight: 600, color: "var(--ink)" }}>How the balance could change</h2>
      <p style={{ margin: "0 0 14px", fontSize: 13, color: "var(--muted)" }}>
        Middle 80% of {result.n_paths} simulated balances &middot; median line &middot; 20 sample paths &middot; threshold {usd0(result.breach_threshold)}
      </p>
      <svg viewBox="0 0 640 250" width="100%" height="auto" role="img"
           aria-label={`${result.n_paths} simulated balance paths across ${result.horizon_weeks} weeks`}>
        {[min, (min + max) / 2, max].map(value => (
          <g key={value}>
            <line className="chart-grid" x1={68} x2={620} y1={y(value)} y2={y(value)} />
            <text className="chart-label" x={62} y={y(value)} textAnchor="end" dominantBaseline="middle">
              {usd0(value)}
            </text>
          </g>
        ))}
        <path className="chart-band" d={`M ${upper} L ${lower} Z`} />
        {samples.map(p => (
          <path key={p.path_id} className="chart-sample" d={`M ${p.balances.map((v, w) => `${x(w)},${y(v)}`).join(" L ")}`} />
        ))}
        <path className="chart-median" d={`M ${median}`} />
        <line className="chart-threshold" x1={68} x2={620} y1={y(result.breach_threshold)} y2={y(result.breach_threshold)} />
        {[0, Math.round(result.horizon_weeks / 2), result.horizon_weeks].map(w => (
          <text key={w} className="chart-label" x={x(w)} y={242}
                textAnchor={w === 0 ? "start" : w === result.horizon_weeks ? "end" : "middle"}>
            Week {w}
          </text>
        ))}
      </svg>
    </div>
  );
}

/** Clean dashboard stat card - the headline numbers, no interactive chrome. */
export function StatsCard({ result }: { result: SimResult }) {
  const headline = result.delta_breach_rate ?? result.baseline_breach_rate;
  const headlineLabel = result.delta_breach_rate === null ? "Baseline breach rate" : "With this decision";

  return (
    <div data-stats-card="true" style={cardStyle}>
      <h2 style={{ margin: "0 0 18px", fontSize: 17, fontWeight: 600, color: "var(--ink)" }}>Simulation summary</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20, marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>{headlineLabel}</div>
          <div style={{ fontSize: 30, fontWeight: 500, marginTop: 6, fontVariantNumeric: "tabular-nums" }}>{percent(headline)}</div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>Baseline breach rate</div>
          <div style={{ fontSize: 30, fontWeight: 500, marginTop: 6, fontVariantNumeric: "tabular-nums" }}>{percent(result.baseline_breach_rate)}</div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>Median minimum balance</div>
          <div style={{ fontSize: 30, fontWeight: 500, marginTop: 6, fontVariantNumeric: "tabular-nums" }}>{usd0(result.median_min_balance)}</div>
        </div>
      </div>
      <p style={{ margin: "0 0 18px", fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
        Of simulated futures fall below {usd0(result.breach_threshold)} at a week end.
      </p>
      <div style={{ borderTop: "1px solid #e4eef4", paddingTop: 16 }}>
        {result.culprit ? (
          <>
            <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>
              {result.culprit.essential ? "Largest essential charge" : "The recurring charge to look at"}
            </div>
            <div style={{ fontSize: 17, fontWeight: 600 }}>{result.culprit.label} &middot; {usd2(result.culprit.amount)}</div>
            <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
              Removing this reduced the breach rate by {points(result.culprit.marginal_contribution)} in this simulation.
            </div>
          </>
        ) : (
          <div style={{ fontSize: 13, color: "var(--muted)" }}>No recurring obligation had a positive measured contribution.</div>
        )}
      </div>
    </div>
  );
}
