const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");

function load(file) {
  const output = ts.transpileModule(fs.readFileSync(`${__dirname}/../lib/${file}.ts`, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const exports = {};
  vm.runInNewContext(output, { exports, require, fetch: global.fetch, AbortSignal, console });
  return exports;
}
const { computeWeeklyBand, sampleRepresentativePaths } = load("fanchart");
const { evidenceAmount } = load("money");
const path = (id, balances) => ({ path_id: id, balances, min_balance: Math.min(...balances), first_breach_week: null });

test("bands use all 500 paths and interpolate percentiles", () => {
  const paths = Array.from({ length: 500 }, (_, i) => path(i, [100, i]));
  const band = computeWeeklyBand(paths);
  assert.equal(band[0].p50, 100);
  assert.ok(Math.abs(band[1].p10 - 49.9) < 1e-10);
  assert.equal(band[1].p50, 249.5);
  assert.ok(Math.abs(band[1].p90 - 449.1) < 1e-10);
});
test("20 representative paths preserve best/worst independent of API ordering", () => {
  const paths = Array.from({ length: 500 }, (_, i) => path(i, [i])).reverse();
  const samples = sampleRepresentativePaths(paths, 20);
  assert.equal(samples.length, 20);
  assert.equal(new Set(samples.map(p => p.path_id)).size, 20);
  assert.equal(samples[0].path_id, 0);
  assert.equal(samples[19].path_id, 499);
  assert.equal(paths[0].path_id, 499);
});
test("raw evidence uses explicit units, supports bills, and never guesses", () => {
  const raw = { amount: 14200 };
  assert.equal(evidenceAmount(raw, "usd_cents"), 142);
  assert.equal(evidenceAmount(raw, "usd"), 14200);
  assert.equal(evidenceAmount({ payment_amount: 145000 }, "usd_cents"), 1450);
  assert.equal(evidenceAmount(raw), null);
  assert.equal(evidenceAmount(raw, "eur"), null);
  assert.equal(evidenceAmount({ amount: "14200" }, "usd_cents"), null);
  assert.equal(evidenceAmount({ amount: Infinity }, "usd"), null);
  assert.equal(raw.amount, 14200);
});
