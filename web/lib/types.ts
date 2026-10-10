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

// One week's p10/p50/p90 across the baseline (no-decision) path set - lets
// the chart overlay baseline vs. decision-scenario without a second full
// 500-path array. Always present (equal to the decision scenario when no
// delta was supplied).
export interface WeeklyBand {
  week: number;
  p10: number;
  p50: number;
  p90: number;
}

export interface SimResult {
  run_id: string;
  seed: number;
  n_paths: number;
  horizon_weeks: number;
  breach_threshold: number;
  baseline_breach_rate: number;
  delta_breach_rate: number | null;
  baseline_band: WeeklyBand[];
  median_min_balance: number;
  culprit: Culprit | null;
  ranked_drivers: Culprit[];
  paths: SimPath[];
  claims: Claim[];
}

export interface TxnRecord {
  [key: string]: unknown;
}

export interface Customer { customer_id: string; name: string }
export interface CashflowModel {
  customer_id: string; opening_balance: number; fit_window_days: number;
  income: { cadence_days: number; mean: number; std: number; next_due_day: number; evidence: string[] };
  recurring: { obligation_id: string; label: string; amount: number; cadence_days: number; essential: boolean; evidence: string[] }[];
  discretionary: { weekly_mean: number; weekly_std: number; by_category: Record<string, number>; evidence: string[] };
  evidence_index: string[];
}
export interface DecisionDelta { kind: string; amount: number; start_day: number; cadence_days: number | null; raw_text: string; label: string }
export interface RunInputs {
  model: CashflowModel; delta: DecisionDelta; evidence: Record<string, TxnRecord>;
  amount_units: { model: string; delta: string; evidence: Record<string, string> };
}
export interface AskResponse {
  run_id: string; prose: string; replay_url: string; validated: boolean;
  rendered_by?: string; render_failure_reason?: string | null;
}
export interface SavedReplay { run_id: string; question: string; customer: string; prose: string; createdAt: string }
