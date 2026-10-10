# web — replay page

```bash
npm install
cp env.example .env         # NEXT_PUBLIC_API_BASE_URL -> Dev B's orchestrator

npm run fixtures:gen          # writes fixtures/sample-run.json (500 paths, ~500KB)
node fixtures/mock-server.mjs # dev-only stand-in for the real API, port 8000
npm run dev                   # http://localhost:3000/r/fixture-run-0001
```

Route: `/r/{run_id}` → `GET {API}/run/{run_id}`. Four sections, in order:
headline, fan chart, culprit panel, provenance table
(`app/r/[run_id]/page.tsx`).

Evidence transaction ids link straight to `GET {API}/txn/{txn_id}` — the
API's own raw JSON, not a page in this app. That's the point: a judge
clicks it and sees a real Nessie record.

**Fan chart performance:** the frozen `SimResult` contract ships full
per-path balances (500 × 104 floats). Rather than wait on a server-side
downsample, `lib/fanchart.ts` computes the p10/p50/p90 band client-side and
draws only ~20 representative polylines on top — never all 500. If Dev A
ships a pre-downsampled `band` field later (Round 3 handshake in
`00-ARCHITECTURE.md`), swap `computeWeeklyBand` for a pass-through.

Deploy to Vercel early with the fixture data — don't wait for a live API to
do the first deploy.

`npm run typecheck` / `npm run build` need no live API — fixtures cover both.
