// Mirrors the frozen contracts in 00-ARCHITECTURE.md. Dev A owns the
// authoritative shapes; this is D's read-only view of them.

export type ClaimKind =
  | "baseline_breach_rate"
  | "breach_rate_with_delta"
  | "culprit_label"
  | "culprit_marginal_contribution"
  | "culprit_amount"
  | "median_min_balance"
  | "first_breach_week"
  | "paths_simulated";

// Common values are "probability" | "usd" | "week" | "count", but
// culprit_label's value is the merchant name itself, not a number, so it
// carries no unit — confirmed live: {"kind":"culprit_label","unit":null}.
export type ClaimUnit = string | null;

export interface Claim {
  claim_id: string;
  kind: ClaimKind;
  // Numeric for every kind except culprit_label, whose value is the label
  // string (matches core.model.Claim.value: float | str).
  value: number | string;
  unit: ClaimUnit;
  evidence: string[];
}

export interface Culprit {
  obligation_id: string;
  label: string;
  amount: number;
  breach_rate_without: number;
  marginal_contribution: number;
  evidence: string[];
  // Present on the live API (core.model.Driver), not in 00-ARCHITECTURE.md.
  essential: boolean;
}

export interface SimPath {
  path_id: number;
  balances: number[];
  min_balance: number;
  first_breach_week: number | null;
}

export interface SimResult {
  run_id: string;
  seed: number;
  n_paths: number;
  horizon_weeks: number;
  breach_threshold: number;
  baseline_breach_rate: number;
  delta_breach_rate: number;
  median_min_balance: number;
  culprit: Culprit;
  ranked_drivers: Culprit[];
  paths: SimPath[];
  claims: Claim[];
}

export interface TxnRecord {
  [key: string]: unknown;
}
