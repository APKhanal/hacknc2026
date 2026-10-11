const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");

// Same loader as contracts.test.cjs: transpile the lib file and run it in a sandbox.
function load(file) {
  const output = ts.transpileModule(fs.readFileSync(`${__dirname}/../lib/${file}.ts`, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const exports = {};
  vm.runInNewContext(output, { exports, require, console, Intl, Date, Math });
  return exports;
}
const s = load("summary");
const CASES = JSON.parse(fs.readFileSync(`${__dirname}/summary-cases.json`, "utf8"));
const [y, m, d] = CASES.today.split("-").map(Number);
const ASKED = new Date(y, m - 1, d);

function makeResult(spec, culprit = null) {
  const paths = spec.paths.map(([balances, fb], i) => ({ path_id: i, balances, min_balance: Math.min(...balances), first_breach_week: fb }));
  return {
    run_id: "r", seed: 1, n_paths: paths.length, horizon_weeks: paths[0].balances.length - 1, breach_threshold: 0,
    baseline_breach_rate: spec.baseline_breach_rate, delta_breach_rate: spec.delta_breach_rate, baseline_band: [],
    median_min_balance: spec.median_min_balance, culprit, ranked_drivers: [], paths, claims: [],
  };
}

// Shared with api/tests/test_summary.py: the text message and the replay must agree.
for (const [rate, expected] of CASES.odds) {
  test(`odds(${rate}) matches the text message`, () => assert.equal(s.odds(rate), expected));
}
for (const c of CASES.cases) {
  test(`verdict and dip match the text message: ${c.name}`, () => {
    const result = makeResult(c.result);
    assert.equal(s.verdictSentence(result, { ...c.delta, raw_text: "", label: "" }, ASKED), c.verdict);
    assert.equal(s.dipSentence(result, ASKED), c.dip);
  });
}

test("without a question date, sentences fall back to relative timing", () => {
  const c = CASES.cases[0], result = makeResult(c.result);
  assert.equal(s.verdictSentence(result, { ...c.delta, raw_text: "", label: "" }, null), "Heads up: spending $2,000 in 7 days would be a real stretch.");
  assert.match(s.dipSentence(result, null), /^Most likely you'd drop below \$0 about 3 weeks in, /);
  assert.equal(s.verdictSentence(result, null, null), "Heads up: this decision would be a real stretch.");
});

test("a recurring charge is only called out when it moves the odds by 5+ points", () => {
  const culprit = (mc) => ({ obligation_id: "o", label: "DoorDash", amount: 57.97, breach_rate_without: 0.9, marginal_contribution: mc, evidence: [], essential: false });
  assert.equal(s.culpritMatters(null), false);
  assert.equal(s.culpritMatters(culprit(0.028)), false);
  assert.equal(s.culpritMatters(culprit(0.05)), true);
});

test("labels read like plain English", () => {
  assert.equal(s.displayName("Jordan Synthetic Seed e3ed4c8012ad"), "Jordan");
  assert.equal(s.displayName("Alex Rivera"), "Alex Rivera");
  assert.equal(s.oddsStat(0.992), "Over 99%");
  assert.deepEqual([0, 3, 52, 104].map(s.weekLabel), ["Today", "Week 3", "1 year", "2 years"]);
  assert.equal(s.horizonLabel(104), "2 years");
  assert.equal(s.weekDate(ASKED, 3), "Oct 31");
});

test("seeded transaction descriptions become readable names; real ones pass through", () => {
  assert.equal(s.describeTransaction({ description: "Synthetic e3ed4c8012ad demo_jordan_doordash_12" }), "DoorDash");
  assert.equal(s.describeTransaction({ description: "Synthetic e3ed4c8012ad demo_jordan_spend_28" }), "Card purchase");
  assert.equal(s.describeTransaction({ description: "Payroll e3ed4c8012ad demo_jordan" }), "Paycheck");
  assert.equal(s.describeTransaction({ description: "Starbucks #1234" }), "Starbucks #1234");
  assert.equal(s.transactionDate({ purchase_date: "2026-03-25" }), "Mar 25, 2026");
  assert.equal(s.transactionDate({}), null);
});

// Multi-item decisions (income + loan + expenses): the same cases api/tests/test_summary.py checks.
for (const c of CASES.decision_cases) {
  test(`decision wording matches the text message: ${c.name}`, () => {
    assert.equal(s.describeDecision(c.decision, ASKED), c.phrase);
    assert.equal(s.decisionNote(c.decision), c.note);
  });
}
