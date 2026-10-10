import type { Culprit } from "@/lib/types";
import { txnUrl } from "@/lib/api";

export function CulpritPanel({ culprit }: { culprit: Culprit }) {
  return (
    <section className="culprit-panel">
      <span className="culprit-eyebrow">the culprit</span>
      <h2 className="culprit-label">{culprit.label}</h2>
      <dl className="culprit-grid">
        <div>
          <dt>amount</dt>
          <dd>${culprit.amount.toFixed(2)}</dd>
        </div>
        <div>
          <dt>marginal contribution to breach rate</dt>
          <dd>+{Math.round(culprit.marginal_contribution * 100)}pp</dd>
        </div>
        <div>
          <dt>breach rate without it</dt>
          <dd>{Math.round(culprit.breach_rate_without * 100)}%</dd>
        </div>
      </dl>
      <div className="culprit-evidence">
        evidence:{" "}
        {culprit.evidence.map((txnId, i) => (
          <span key={txnId}>
            {i > 0 && ", "}
            <a href={txnUrl(txnId)} target="_blank" rel="noreferrer" className="txn-link">
              {txnId}
            </a>
          </span>
        ))}
      </div>
    </section>
  );
}
