# Manual Pocketwatch workflow test

The browser/cached-data workflow has been verified. Photon/iMessage and live
Gemini generation still need manual verification. A key being present does not
establish that credentials, quota, or provider connectivity work.

## 1. Test the browser workflow now

Open http://127.0.0.1:3000. The frontend and cached API were left running on
ports 3000 and 8002. Start with those services; do not start duplicate workers.

1. Click **Overview**. Select **Alex Synthetic Seed** from Demo profile.
2. Enter exactly `Can I afford $1400 today?` and click **Run simulation** once.
3. You should land at `/r/{new-run-id}` and see:
   - Alex, 500 paths, 104 weeks;
   - decision breach rate **4%**, baseline **0%**;
   - median minimum balance **$561.44**;
   - Geico **$142**, marginal contribution **1 percentage point**.
4. Move the week slider to week 1. The three values should be
   **$585.24 / $705.39 / $818.48**.
5. Open **Saved model & evidence**. Opening balance should be **$2,310.40**.
   Check transaction paging and an evidence record. A Geico record should show
   `$142.00`, unit `usd_cents`, and raw JSON `amount: 14200`.
6. Close evidence with Escape. Focus should return to its button. Reload the
   replay; the saved model should remain unchanged.
7. Minimize the window, then restore it from the taskbar. The same run should
   remain open. Test maximize/restore and Copy replay link.
8. Return to Overview, select **Drew Synthetic Seed**, and ask the same question.
   Expect **0%** and **No contributing recurring charge**.

## 2. Exercise errors and desktop behavior

- Ask `Can I afford a car?`: expect an amount/timing error and retained text.
- Open `/r/missing`: expect a missing-replay page with a link back.
- Save a draft, open Scenarios, use it, remove it and Undo.
- Change appearance, reload, verify the setting, then restore your preference.
- At phone width, check that the composer, window scrolling and evidence dialog
  remain usable. The wallpaper is intentionally static.
- To test a service outage, stop **only your local API** in its terminal and
  submit a valid question. Expect an unavailable-service error and retained
  text. Restart the API, then explicitly retry. No submission is retried
  automatically. If the API was started by Codex, ask Codex to stop that worker
  before launching your own.

## 3. Startup commands when services are not running

From the repository root, terminal A:

```sh
GEMINI_API_KEY= COUNTERFACTUAL_CACHE_DIR=data/cache/seeded COUNTERFACTUAL_DB_PATH=data/cache/seeded/frontend-verification.sqlite3 COUNTERFACTUAL_PARSER=explicit REPLAY_BASE_URL=http://127.0.0.1:3000 .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8002
```

Terminal B, from `web`:

```sh
npm run dev -- --hostname 127.0.0.1
```

`web/.env.local` should contain `API_BASE_URL=http://127.0.0.1:8002`.
This first stage uses actual cached bank records, core simulation and SQLite,
but intentionally disables paid generation.

## 4. Test inbound iMessage → simulation → reply → replay

Create `agent/.env` from `agent/env.example`. Fill credentials locally:

```dotenv
PROJECT_ID=your-photon-project-id
PROJECT_SECRET=your-photon-project-secret
API_BASE_URL=http://127.0.0.1:8002
REPLAY_BASE_URL=http://127.0.0.1:3000
CUSTOMER_PHONE_MAP={"+1YOURNUMBER":"39b2bdb2-e13c-4734-8522-1e2d43df6d1f"}
ENABLE_REACTION_RERUN=false
```

The map key must match the sender ID delivered by Photon; the code currently
uses `message.sender.id`. Do not put credentials into chat or commit `.env`.

From `agent`, run `npm run dev`. Confirm that it connects and prints its
listening message, and that the Photon project's iMessage number is connected.
From your mapped phone, send `Can I afford $1400 today?` to that number.

Expected: typing indicator, prose reply, a separate replay link, then two
more messages with clean image cards as iMessage attachments: a stats card
(breach rate, baseline, median balance, the culprit if any) and a graph card
(band, median line, threshold) — purpose-built static cards, not a screenshot
of the interactive replay page's slider/table chrome. The API terminal should
record `POST /ask` returning 200. Open the replay and verify Alex's result
and evidence as above. Keep reactions disabled for this test.

**Cards alone:** `GET {frontend}/api/stats/{run_id}` and
`GET {frontend}/api/chart/{run_id}` render those cards via a headless
screenshot of the non-interactive `/r/{run_id}/export` page and return
`image/png`; a missing `run_id` returns 404 on either. Hit them directly in a
browser or with curl to check the images without going through Photon.

**Fast, no-Gemini demo path:** texting the agent exactly `test1` through
`test5` (case-insensitive) runs the real simulation against one of five
synthetic profiles (`test1`→Alex, `test2`→Blair, `test3`→Casey, `test4`→Drew,
`test5`→Ellis), skips Gemini entirely, and replies in well under a second
with `rendered_by: "test_fixture"` — useful for a reliable on-stage
demonstration independent of network conditions. Set
`COUNTERFACTUAL_TEST_TRIGGERS=0` on the API to disable this and fall back to
normal parsing for those strings.

**Phone link routing:** `127.0.0.1` on a phone means the phone itself. For the
link to open directly there, use a frontend URL reachable from the phone
(for example, your deployed frontend or a tunnel to local port 3000). Set that
URL as `REPLAY_BASE_URL` on the **API** and restart it; use the same origin in
the agent configuration. The agent prefers the API's absolute replay URL, so
its environment alone cannot override a localhost URL. The frontend still
needs an API origin reachable from wherever its Next.js server runs.

For an initial local smoke test, you can instead open the received localhost
link on this Mac. That verifies messaging and replay generation, but does not
verify phone access to the frontend.

## 5. Test live generation and fresh Nessie ingestion separately

To include Gemini, stop the local API and restart the same command with the
`GEMINI_API_KEY=` prefix removed. It can then load the existing key from root
`.env`. Configure `GEMINI_MODEL` for a model available to that key. Ask a fresh
question such as `Can I afford $1437 today?` so an earlier prose cache hit is
less likely. Inspect `/api/backend/ask` in browser DevTools → Network:

- `validated: true` and a working replay are the functional success criteria.
- `cache_hit` proves reuse, not a new Gemini request.
- `template_fallback` and `render_failure_reason` explain an upstream failure;
  the checked simulation may still be successful.
- Confirm actual provider usage with a configured key to establish live Gemini
  execution. `gemini_rendered` alone is insufficient because the no-key renderer
  can return local fallback prose that main currently labels the same way.

The browser and messaging paths read cached Nessie data; they do not fetch
Nessie on every question. To verify a fresh read from Nessie, from the repo root:

```sh
.venv/bin/python -m data.ingest --population owned --customer-id 39b2bdb2-e13c-4734-8522-1e2d43df6d1f --cache-dir data/cache/seeded
```

Check the ingest report for success, restart the API to load the refreshed
cache, then repeat Alex's test. This is read-only ingestion of the existing
seeded customer. Data changes can change simulation results; expected figures
above describe the verified cached population.

The complete manual gate is: fresh ingestion succeeds → mapped iMessage is
received → API persists a validated run → reply and reachable replay URL arrive
→ the phone opens that same saved result → evidence amounts and raw units match.
Live Gemini execution is an additional provider check; safe template fallback
is an intentional supported behavior.
