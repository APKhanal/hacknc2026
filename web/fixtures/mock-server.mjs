// Tiny stand-in for the FastAPI orchestrator, serving only the two routes
// the replay page needs. Dev-only: `node fixtures/mock-server.mjs`.
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const run = JSON.parse(readFileSync(join(__dirname, "sample-run.json"), "utf8"));

const server = createServer((req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");

  if (req.url === `/run/${run.run_id}`) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(run));
    return;
  }

  const txnMatch = req.url?.match(/^\/txn\/(.+)$/);
  if (txnMatch) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(
      JSON.stringify({
        txn_id: decodeURIComponent(txnMatch[1]),
        merchant: "Geico",
        amount: 142.0,
        date: "2026-01-12",
        note: "mock record — this is fixtures/mock-server.mjs, not live Nessie data",
      })
    );
    return;
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "not found" }));
});

const port = 8000;
server.listen(port, () => {
  console.log(`mock API listening on http://localhost:${port}`);
  console.log(`try: http://localhost:3000/r/${run.run_id}`);
});
