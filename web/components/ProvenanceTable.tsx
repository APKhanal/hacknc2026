import type { Claim } from "@/lib/types";
import { txnUrl } from "@/lib/api";

function formatValue(claim: Claim): string {
  switch (claim.unit) {
    case "probability":
      return `${Math.round(Number(claim.value) * 100)}%`;
    case "usd":
      return `$${Number(claim.value).toFixed(2)}`;
    case "week":
      return `week ${claim.value}`;
    case "count":
      return `${claim.value}`;
    default:
      return `${claim.value}`;
  }
}

export function ProvenanceTable({ claims }: { claims: Claim[] }) {
  return (
    <section className="provenance">
      <span className="section-eyebrow">every claim, traced</span>
      <table className="provenance-table">
        <thead>
          <tr>
            <th>claim</th>
            <th>value</th>
            <th>evidence</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.claim_id}>
              <td>{claim.kind.replaceAll("_", " ")}</td>
              <td>{formatValue(claim)}</td>
              <td>
                {claim.evidence.length === 0 ? (
                  <span className="muted">none</span>
                ) : (
                  claim.evidence.map((txnId, i) => (
                    <span key={txnId}>
                      {i > 0 && ", "}
                      <a
                        href={txnUrl(txnId)}
                        target="_blank"
                        rel="noreferrer"
                        className="txn-link"
                      >
                        {txnId}
                      </a>
                    </span>
                  ))
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
