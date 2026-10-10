import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { askOrchestrator, AskClarificationError } from "../src/askClient.js";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test("forwards a backend clarification without HTTP or JSON clutter", async () => {
  globalThis.fetch = async () => new Response(
    JSON.stringify({ detail: "Please include an amount and payment date." }),
    { status: 422 },
  );
  await assert.rejects(askOrchestrator("http://api.test", "a flight", "demo", 1000),
    (err: unknown) => err instanceof AskClarificationError &&
      err.message === "Please include an amount and payment date.");
});

test("does not classify server failures as user clarification messages", async () => {
  globalThis.fetch = async () => new Response(
    JSON.stringify({ detail: "Internal server failure" }), { status: 503 },
  );
  await assert.rejects(askOrchestrator("http://api.test", "$1400 today", "demo", 1000),
    (err: unknown) => err instanceof Error && !(err instanceof AskClarificationError));
});

test("preserves the response paragraphs for iMessage", async () => {
  const prose = "This expense increases your risk.\n\nWith this expense: 20%\nWithout it: 12%";
  globalThis.fetch = async () => new Response(JSON.stringify({
    run_id: "run", prose, replay_url: "https://replay.test/r/run", validated: true,
  }), { status: 200 });
  const result = await askOrchestrator("http://api.test", "$1400 today", "demo", 1000);
  assert.equal(result.prose, prose);
});
