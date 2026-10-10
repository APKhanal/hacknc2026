// Generates a SimResult fixture matching the frozen contract in
// 00-ARCHITECTURE.md, for local dev of the replay page without a live API.
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

const N_PATHS = 500;
const HORIZON_WEEKS = 104;
const OPENING_BALANCE = 2310.4;
const BREACH_THRESHOLD = 0.0;

function randn() {
  const u1 = Math.random();
  const u2 = Math.random();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

function simulatePath(pathId) {
  let balance = OPENING_BALANCE;
  const balances = [balance];
  let firstBreachWeek = null;
  for (let w = 1; w <= HORIZON_WEEKS; w++) {
    balance += 1850 / 2 - 210 + randn() * 90;
    balances.push(Math.round(balance * 100) / 100);
    if (firstBreachWeek === null && balance < BREACH_THRESHOLD) {
      firstBreachWeek = w;
    }
  }
  return {
    path_id: pathId,
    balances,
    min_balance: Math.round(Math.min(...balances) * 100) / 100,
    first_breach_week: firstBreachWeek,
  };
}

const paths = Array.from({ length: N_PATHS }, (_, i) => simulatePath(i));
const breachCount = paths.filter((p) => p.first_breach_week !== null).length;
const breachRate = Math.round((breachCount / N_PATHS) * 1000) / 1000;

const fixture = {
  run_id: "fixture-run-0001",
  seed: 1337,
  n_paths: N_PATHS,
  horizon_weeks: HORIZON_WEEKS,
  breach_threshold: BREACH_THRESHOLD,
  baseline_breach_rate: 0.11,
  delta_breach_rate: breachRate,
  median_min_balance: paths.map((p) => p.min_balance).sort((a, b) => a - b)[
    Math.floor(N_PATHS / 2)
  ],
  culprit: {
    obligation_id: "rec_01",
    label: "Geico",
    amount: 142.0,
    breach_rate_without: 0.08,
    marginal_contribution: 0.19,
    evidence: ["txn_111", "txn_222", "txn_333"],
  },
  ranked_drivers: [],
  paths,
  claims: [
    {
      claim_id: "c1",
      kind: "baseline_breach_rate",
      value: 0.11,
      unit: "probability",
      evidence: ["txn_abc"],
    },
    {
      claim_id: "c2",
      kind: "breach_rate_with_delta",
      value: breachRate,
      unit: "probability",
      evidence: ["txn_abc", "txn_def"],
    },
    {
      claim_id: "c3",
      kind: "culprit_label",
      value: 0,
      unit: "count",
      evidence: ["txn_111"],
    },
    {
      claim_id: "c4",
      kind: "culprit_marginal_contribution",
      value: 0.19,
      unit: "probability",
      evidence: ["txn_111", "txn_222"],
    },
    {
      claim_id: "c5",
      kind: "first_breach_week",
      value: 31,
      unit: "week",
      evidence: ["txn_444"],
    },
  ],
};

writeFileSync(join(__dirname, "sample-run.json"), JSON.stringify(fixture));
console.log(`wrote fixtures/sample-run.json (${JSON.stringify(fixture).length} bytes)`);
