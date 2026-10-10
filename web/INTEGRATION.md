# Pocketwatch frontend integration

Verified locally on 2026-10-10 against the cached seed population and the actual
FastAPI/core pipeline. This supersedes the prototype-only status in
`docs/frontend/VERIFICATION.md`; that file remains a historical design review.

## Contracts reviewed

`00-ARCHITECTURE.md`, `SESSION_HANDOFF.md`, `READY-FOR-INTEGRATION.md`,
`docs/frontend/DESIGN.md`, `docs/MONEY_UNITS.md`, `data/HANDSHAKE_NOTES.md`,
`core/HANDSHAKE_NOTES.md`, and the Dev C integration notes were checked against
`api/main.py`, `api/store.py`, and `core/model.py`. Some older handoffs describe
a four-field answer and a render retry. Main now returns rendering metadata,
passes the culprit to validation, and attempts rendering once.

## Local startup

Install Python dependencies from the repo root and frontend dependencies in `web`:

```sh
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]' google-generativeai requests
cd web
npm ci
cp env.example .env.local
```

From the repo root, this uses the existing synthetic cache, a separate local
verification database, and disables paid Gemini calls:

```sh
GEMINI_API_KEY= COUNTERFACTUAL_CACHE_DIR=data/cache/seeded COUNTERFACTUAL_DB_PATH=data/cache/seeded/frontend-verification.sqlite3 COUNTERFACTUAL_PARSER=explicit REPLAY_BASE_URL=http://127.0.0.1:3000 .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8002
```

In another terminal, run `npm run dev` from `web` and open
http://127.0.0.1:3000. `.env.local` should contain
`API_BASE_URL=http://127.0.0.1:8002`. If that port already runs the API, reuse it
instead of starting a second worker. A fresh checkout without the seed cache
can use `python -m data.demo` and `COUNTERFACTUAL_CACHE_DIR=data/cache/demo`.

## Connected behavior

- Overview loads `/customers` and `/model/{customer_id}`. Submission sends
  exactly one `{text, customer_id}` request to `/ask`. It disables duplicate
  submissions, reports waiting status after four seconds, preserves input on
  errors, and routes a validated response to the local `/r/{run_id}` page.
- Replay loads the simulation and the **saved** `/run/{id}/inputs` in parallel.
  Null contributors are supported. Rates retain a zero value; marginal
  contributions use percentage points. Evidence IDs open a native keyboard
  accessible dialog; Escape returns focus to the originating button.
- Chart bands derive p10/p50/p90 from all 500 paths with linear interpolation.
  Twenty paths span the ranking by minimum balance and include both extremes.
  The week slider provides the same values as a numeric table.
- `?view=model` opens original saved assumptions and transactions, ordered
  newest first with ten per page. `?txn={id}` opens a record. Raw JSON remains
  untouched. Only an explicit `usd_cents` unit divides an amount by 100;
  missing or unsupported units display unavailable.
- Desktop icons, Start navigation, minimize/restore, maximize/restore and close
  are wired. Restoring a minimized replay preserves its run URL. Drafts have
  save/use/remove/undo behavior. Appearance persists through reload. The static
  user-supplied wallpaper, logo, and XP icon styling remain intact.

## Verification evidence

- `npm run typecheck`, `npm run build`, and three frontend contract tests pass.
- Agent `npm run typecheck` passes. Python suite: **142 passed**. The earlier
  three failures were outdated response/retry expectations; tests now cover
  the current one-attempt renderer, three-argument validator and cache hit.
  Rendering cache and Gemini key are isolated in tests.
- Browser: Alex's $1,400 decision gives 4% versus a 0% baseline, Geico $142,
  and a 1 percentage point contribution. Drew gives 0% and no contributor.
- Week 1 browser values `$585.24 / $705.39 / $818.48` match NumPy's full-path
  percentiles `[585.238, 705.39, 818.48]` after display rounding.
- Live proxy: all six cached customer models fit; all 102 original Alex
  evidence records and unit headers match the saved inputs exactly. Unknown
  resources return 404 and unsupported questions return 422 through the proxy.
- Browser outage test returns the proxy's 503 message and keeps the question.
  Replay reload retains the saved opening balance of $2,310.40. Transaction
  paging, Escape/focus return, replay copying, drafts/undo, appearance reload,
  Start navigation and window controls were checked.
- At 390 × 844, composer and evidence dialog fit without page overflow;
  dialog width is 356px. Viewport was reset after testing.

Repeat the read-only live proxy check using a saved run from your API:

```sh
VERIFY_RUN_ID=your-run-id .venv/bin/python web/tests/verify_live.py
```

## Limits and remaining external setup

This verifies browser → local API → cached data → core → persisted replay → UI.
It does not verify live Nessie ingestion, paid Gemini generation, deployment, or
Photon/iMessage delivery. No messages were sent. `agent/.env` is absent, so
Photon credentials and the phone/customer map still need configuring before
that separate channel can run. Align its API and replay origins with these
local ports.

The renderer's null-contributor assumption was fixed and covered by a regression
test. The API still uses checked templates when prose validation fails.
The no-key renderer can also return fallback text that main labels as
`gemini_rendered`; do not use that metadata alone as proof of a live Gemini
call. These are upstream renderer limitations, not verified cloud behavior.
The installed Google SDK and Starlette test client emit deprecation warnings.
