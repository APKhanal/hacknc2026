const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");

// Load lib/auth.ts with an in-memory localStorage (same loader idea as contracts.test.cjs).
function load() {
  const output = ts.transpileModule(fs.readFileSync(`${__dirname}/../lib/auth.ts`, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const store = new Map();
  const localStorage = { getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k) };
  const exports = {};
  vm.runInNewContext(output, { exports, require, localStorage, Date, JSON, Error });
  return exports;
}

test("every demo account maps to a distinct customer and never exposes its password", () => {
  const auth = load();
  assert.equal(new Set(auth.DEMO_ACCOUNTS.map(a => a.customerId)).size, auth.DEMO_ACCOUNTS.length);
  for (const profile of auth.LOGIN_PROFILES) assert.equal("password" in profile, false);
});

test("sign in with the right password, case-insensitive email; sign out clears it", async () => {
  const auth = load();
  assert.equal(auth.getSession(), null);
  const session = await auth.signIn("  JORDAN@pocketwatch.tech ", "jordan-aero");
  assert.equal(session.user.customerId, "7b3e4794-645b-481b-b8d1-a7a1ebffee47");
  assert.equal("password" in session.user, false);
  assert.equal(auth.getSession().user.name, "Jordan");
  await auth.signOut();
  assert.equal(auth.getSession(), null);
});

test("wrong password or unknown email is rejected with one generic message", async () => {
  const auth = load();
  await assert.rejects(auth.signIn("jordan@pocketwatch.tech", "nope"), /Incorrect email or password/);
  await assert.rejects(auth.signIn("nobody@pocketwatch.tech", "jordan-aero"), /Incorrect email or password/);
  assert.equal(auth.getSession(), null);
});

test("post-login redirects only go to paths on this site", () => {
  const { safeNext } = load();
  assert.equal(safeNext("/?view=replays"), "/?view=replays");
  assert.equal(safeNext("https://evil.example"), "/?view=overview");
  assert.equal(safeNext("//evil.example"), "/?view=overview");
  assert.equal(safeNext(null), "/?view=overview");
});
