# Pocketwatch / Aero foundation

The previous frontend and its gallery assets have been removed. This is a new
product workspace, built with the existing Next.js, TypeScript and Tailwind toolchain.
The imagegen reference is `aero-workspace-reference.png`; its exact prompt is
`reference-prompt.txt`. The image is an art-direction reference, never rendered
as an interface screenshot in the app.

## Extracted design system

- One floating app window: 1340px maximum width, 20px radius, a translucent cyan
  outer rim, white inner highlight and blue ambient shadow. No decorative window
  close/minimize controls that cannot act on the browser.
- Header: 70px; sidebar: 218px; main gutters: 34px. The user-supplied backgrounds remain selectable in Preferences and visible
  around the window, while white content dominates the page.
- Humanist system typography: Segoe UI / system sans. Headline 32px/1.2,
  section heading 18px, body 14px, supporting text 12–13px. Ink #14334d;
  secondary #59758b. User-selected Frutiger Aero takes precedence over skills'
  generic font and gradient preferences.
- Four signature components: glass window shell, inset content panel,
  gel button, and layered-glass empty state. Panels use a white rim and a
  subtle cyan border. Controls use a top specular highlight and a sharp middle
  gradient stop. Radii: window 20px, panel 14px, controls 10px.
- Ocean cyan primary; optional meadow green accent. The supplied backgrounds set the sky-blue and grass-green atmosphere. No fake balances, simulated probabilities or connection claims.
- Motion: brief staggered fade-up on entering a view; tactile button presses.
  No perpetual decorative motion. Reduced-motion and reduced-transparency states.
- Below 760px the sidebar becomes a four-item navigation row; content becomes
  one column. Below 480px actions wrap and the window gutters shrink.

## Foundation behavior

Overview and Scenarios save local drafts in browser storage. Drafts never run a
simulation or call the bank. Replays accepts a real run ID and opens the existing
API-backed replay contract. Preferences changes the accent and transparency.
Storage failures produce an inline message and keep the draft available in memory.

The replay presentation is also rebuilt with the new primitives. It reads the
existing SimResult contract, displays real returned values, and links evidence
transaction IDs to the API. Backend contracts and simulation code are unchanged.

Background sources are the user-supplied images. The generated wallpaper
was removed after the user supplied those assets. The generated UI reference
remains development documentation only.

## XP desktop revision

The user supplied an XP desktop screenshot and requested icon-driven navigation.
That screenshot supersedes the generated workspace reference for window chrome
and layout. The initial screen now shows the wallpaper, four app icons and an XP
taskbar. Opening a page displays a smaller 780px window with a blue beveled title
bar, three working controls and translucent content. Windows minimize into the
taskbar and close to the desktop. Pointer dragging and double-click maximize are
supported. The original three user-supplied images remain selectable alongside the Water world wallpaper.

## Skeuomorphic icon revision

The user requested XP-era Luna / Aqua-adjacent / web 2.0 gloss. Desktop navigation
now uses standalone transparent raster illustrations: an ivory computer with a
blue glass screen, a golden folder with documents and calculator, an aqua clock
with a green rewind arrow, and polished control-panel gears. Each uses matching
three-quarter perspective, rounded beveled edges, top-left highlights and a soft
contact shadow. No square app tile surrounds the objects. The same assets are
used in all application-navigation surfaces; window controls remain compact glyphs.

## Water world finish

Use the supplied 1920×1080 water/globe/city artwork as the default full-bleed wallpaper. Keep the XP desktop interaction and illustrated icons. Refine existing surfaces with pale cyan edge reflections, gloss split highlights, translucent aqua panels, and water-blue shadows. Keep content readable and respect the glass-surface preference.
