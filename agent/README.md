# agent — Photon/Spectrum iMessage agent

```bash
npm install
cp env.example .env    # fill in SPECTRUM_PROJECT_ID/SECRET from the Photon dashboard,
                         # API_BASE_URL (Dev B's orchestrator), CUSTOMER_PHONE_MAP
npm run dev              # watches src/, restarts on change
```

Flow: inbound iMessage → typing indicator → `POST {API_BASE_URL}/ask` →
reply with prose → send the replay URL. One HTTP call, no Python, no auth —
just a hardcoded phone → `customer_id` map in `.env`.

If `/ask` errors or times out, the agent sends a human fallback message
instead of going silent (`src/index.ts`, `handleAsk`).

`ENABLE_REACTION_RERUN=true` turns on the optional thumbs-up re-run: react
👍 to a result to re-ask with "assume I go ahead with it" applied. Off by
default — cut it without hesitation if it's not cheap before the demo.

`npm run typecheck` — no credentials needed, just validates the code.
