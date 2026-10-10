import type { SimResult } from "@/lib/types";

function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

export function Headline({ result }: { result: SimResult }) {
  return (
    <section className="headline">
      <div className="headline-stat">
        <span className="headline-label">without the decision</span>
        <span className="headline-number">{pct(result.baseline_breach_rate)}</span>
      </div>
      <div className="headline-arrow">→</div>
      <div className="headline-stat">
        <span className="headline-label">with the decision</span>
        <span className="headline-number headline-number--delta">
          {pct(result.delta_breach_rate)}
        </span>
      </div>
    </section>
  );
}
