# Pocketwatch frontend

A fresh Frutiger Aero app foundation built with Next.js App Router, React,
TypeScript, Tailwind v4 and lucide-react. The previous frontend is removed.

```bash
npm ci
npm run dev
```

Open http://localhost:3000. `npm run typecheck` and `npm run build` verify the app.
Copy `env.example` to `.env.local` and set server-side `API_BASE_URL` to the
simulation service (the seeded local setup uses http://127.0.0.1:8002).
Browser requests use the allowlisted same-origin `/api/backend` proxy; no CORS
configuration is required. See [INTEGRATION.md](INTEGRATION.md) for startup and verified flows.

## Foundation

- `/`: wallpaper desktop with four application icons and a Start menu.
- `/?view=overview`: decision composer, saved scenarios and workspace status.
- `/?view=scenarios`: locally saved scenario drafts.
- `/?view=replays`: open a replay by run ID.
- `/?view=preferences`: four supplied backgrounds, ocean/meadow accents and optional glass surfaces.
- `/r/{run_id}`: API-backed simulation results and transaction evidence.

Scenario drafts and appearance preferences stay in browser localStorage; they
are not sent to the API or run through the simulation. The overview deliberately
starts empty. The composer loads cached profiles and their fitted models, sends one `/ask`
request, and opens only a validated saved replay. Questions survive API errors;
recent replay links and returned prose stay in this browser.
Storage failures preserve the current session and show a message.

Reusable primitives live in `components/ui/aero.tsx`. The shared layout lives
in `components/workspace/app-shell.tsx`; view behavior lives in `workspace.tsx`.
Global tokens, component styles and breakpoints live in `app/globals.css`.
`replay-result.tsx` displays saved models, explicit-unit evidence, all-path
percentile bands, a week inspector, and 20 paths ranked by minimum balance.
`components.json` configures shadcn imports into `@/components/ui`, with `cn`
in `lib/utils.ts`. The API contract and statistical helpers stay in `lib/`.

`design/DESIGN.md` records the extracted proportions, palette, state behavior,
responsive behavior and component system. `design/aero-workspace-reference.png`
is the built-in imagegen design reference, with its exact generation prompt in
`design/reference-prompt.txt`. The backgrounds in `public/images/` are copies of the images supplied by
the user: `aero-green-city.jpg`, `aero-globe-city.jpg` and `aero-globe-flight.jpg`.
The default water/globe/city wallpaper and Pocketwatch clock logo are also user-supplied.
The four desktop icons are generated illustrations; wallpapers are static.
The app is implemented as accessible HTML and React components, not an embedded
image of a UI. Both motion and transparency preferences are supported.

Replay fixture development:

```bash
npm run fixtures:gen
node fixtures/mock-server.mjs
```

Set `API_BASE_URL` to the mock server origin, then open the Replays view and
enter `fixture-run-0001`. The mock is for replay development, not the real `/ask` flow.

## Desktop interaction

Click or keyboard-activate an icon to open its application. The taskbar tracks
opened applications and restores minimized pages. Only the active page is visible;
other opened pages stay available through their taskbar buttons. Close removes
the active application from the taskbar. Browser back/forward and direct query
URLs restore the selected application. Drafts and preferences remain independent
of window state.

The title bar supports pointer dragging, double-click maximize/restore, and
labeled minimize/maximize/close buttons. Windows are capped at 780px wide and
680px high; longer pages scroll inside the window. Maximize fills the desktop
above the taskbar. Smaller screens use a two-column icon grid and a scrollable
window below the icons. The supplied wallpaper images remain visible
around the window and subtly through its content. Glass can be disabled in
Preferences, and reduced-transparency settings also use solid surfaces.

## Desktop icon artwork

Desktop application icons are original transparent PNG illustrations in
`public/images/icons/xp-{overview,scenarios,replays,preferences}.png`. The same
artwork appears at smaller sizes in window titles, taskbar entries and the Start
menu. The icons use dimensional XP/Luna/Aqua-era objects rather than line glyphs
inside app tiles. Window control glyphs remain lucide-react.

The icons were made with built-in imagegen; the full prompt set is recorded in
`design/xp-icon-prompts.json`. Served assets are resized to 128px for crisp 64px
icons on high-density displays. Click targets and keyboard navigation are unchanged.

The default wallpaper is the user-supplied `public/images/aero-water-world.png`. Appearance settings offer Water world and the three earlier backgrounds. The wallpaper revision migrates older saved appearance settings to Water world once while retaining drafts and accent/glass preferences. Aqua highlights refine the existing XP chrome, gel buttons, and panels.
