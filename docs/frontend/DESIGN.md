# Counterfactual: Carolina Aero

UI/UX design proposal and local interaction prototype, October 10, 2026.

## Direction

Reading this as a financial scenario and replay interface for demo users, with
optimistic Frutiger Aero materials and Carolina blue accents. The experience is
light, tactile, and readable. A person asks about an expense, explores simulated
balances, and opens the evidence behind the result.

Design dials: **variance 5 / motion 3 / density 3**. The entry page has an
asymmetric composition; replay uses a predictable reading order. Motion gives
button feedback and short state transitions. There is no continuous floating,
scroll hijacking, or moving chart decoration.

The user's Frutiger Aero reference takes precedence over taste-skill defaults:
white, gloss, blue gradients, and a light-only theme are deliberate. Taste's
landing-page guidance applies to the entry surface; its marketing-layout rules
do not determine the replay's data presentation. Native, accessible controls are
the basis for this prototype; the production architecture remains Next.js.

## Visual references and extraction

Generated screen images are composition references, not screenshots of a live
API. Illustrated charts and sample records in those images are not authoritative
data. The clickable prototype uses results from the actual Python simulator.

| Reference | Translate into UI | Deliberate correction |
| --- | --- | --- |
| [Desktop entry](references/01-entry-desktop.png) | Left-aligned headline; one translucent form; water sphere at right; open explanation row | Scale heading and form to keep the action visible at 1366 × 768; navy button text |
| [Desktop replay](references/02-replay-desktop.png) | Dominant probability; wide white chart surface; separate contributor aside | Use actual paths, actual opening balance, and derived percentile band; avoid white text on light blue |
| [Mobile replay](references/03-replay-mobile.png) | Question, probability, chart, contributor, next action in that order | Stack comparison at narrow widths; remove unnecessary nested panels; keep at least 44px targets |
| [Evidence](references/04-evidence-desktop.png) | Model tab and opaque evidence sheet; original record disclosure | Actual dates/amounts/IDs only; units are transport metadata, never added to raw JSON |

The entry uses a 1200px content width with 32-64px outer gutters, a 560px form,
and a headline at 52px desktop / 36px mobile. Header height is 72px. Form padding
is 26px. Inputs are at least 48px high. Main section gaps are 40-64px.

Replay uses a roughly 2.3:1 chart/aside ratio at desktop. It collapses at 900px.
The chart is the main visual object. Its reading plane is almost opaque white;
glass is reserved for the header, form, contributor panel, and navigation.

Four signature components: glossy primary action, frosted question form,
percentile fan chart, and evidence sheet. State-transition cues: brief fade-in
on the result and smooth disclosure of supporting information. No decorative
motion is needed to recognize the aesthetic.

## Color and material tokens

| Token | Value | Use |
| --- | --- | --- |
| Carolina blue | `#4B9CD3` | Brand accents, selected surfaces, chart samples |
| Carolina mist | `#EAF5FC` | Page and secondary surfaces |
| White | `#FFFFFF` | Reading surfaces, glass highlights |
| Navy | `#13294B` | Primary text, chart median, button labels |
| Deep blue | `#17638F` | Links and active controls on light backgrounds |
| Secondary ink | `#435E76` | Helper text, legends, axis labels |
| Hairline | `#BDD7E8` | Surface edges and separators |
| Error | `#922F38` | Error text with an explicit message, never color alone |

The Carolina blue value is grounded in UNC's published digital palette. Its
white contrast is insufficient for small button text, so primary buttons use
navy labels. Accent color never substitutes for a focus outline or text label.

Glass: white at 90% opacity, 12px blur, 1px white top highlight, blue tinted
shadow. Provide opaque fills without backdrop-filter and under reduced
transparency. Chart/table surfaces use at least 97% white.

Gloss: a convex blue gradient with a deliberate midpoint transition, white
inset highlight, and a restrained shadow. No glow behind paragraphs.

Type: `Segoe UI`, with system humanist sans fallbacks. Body 16px / 1.55;
small text 14px minimum; section heading 24px; prominent probability 64px.
Numbers use tabular numerals. No external font request is needed.

Shape: 18px large surfaces, 10px inputs, pill actions. Space scale:
4 / 8 / 12 / 16 / 24 / 32 / 48 / 64. Layer scale: normal 0, header 10,
native modal top layer. No nested glass shells.

## Information architecture

| Production location | Job | Data |
| --- | --- | --- |
| `/` | Choose a demo profile and ask about an expense | `GET /customers`, `POST /ask` |
| `/r/{run_id}` | Read result and inspect balance paths | `GET /run/{run_id}` plus saved inputs |
| `/r/{run_id}?view=model` | Explain fitted income, recurring charges, and evidence | `GET /run/{run_id}/inputs` |
| `/r/{run_id}?view=model&txn={id}` | Open a shareable evidence detail | Saved evidence or `GET /txn/{id}` |

The web question form complements the existing iMessage flow. A Photon link
opens directly into replay, without requiring a detour through the entry page.
Preserve `/r/{run_id}` and the frozen API response shape.

### Entry and request states

1. Show a labelled demo-profile selector and question textarea. State clearly
   that the bank population is synthetic.
2. Example buttons fill the question; they never submit immediately.
3. Submit once. Keep the question visible; disable repeat submission while the
   request is pending. Announce “Exploring possible balances…” in a polite live
   region. Preserve the selected customer and draft on errors.
4. After 4 seconds of an unresolved request, show “Still working on your
   question…” without claiming a specific backend phase. This is a per-request
   web state. The decision to enable Photon interim messages still depends on
   the deployed full-path `/ask` p50 measurement discussed separately.
5. A validated success navigates to its replay. Render `prose` as text, not HTML.
   `validated: true` means checked output; never label it “Gemini verified.”

| Condition | UX |
| --- | --- |
| Empty question | Inline prompt next to field; focus field |
| 422 parse | API `detail` with a concrete amount/timing example |
| 422 data fit | Explain that this profile cannot support a model; offer another profile |
| 404 customer | Refresh profile list while preserving the question |
| 503 / network failure | Keep draft; explain failure; explicit retry |
| Long request | Persistent status; no fabricated percentage progress |
| Replay missing | “This replay could not be found.” and a new-question link |
| Empty customer list | Explain that no demo profiles are available; disable submission |
| Chart fetch failure | Keep any already loaded summary, show retry inside chart region |

Retries of `/ask` are user initiated: requests create saved runs, and automatic
retries after uncertain delivery could create duplicates. Do not automatically
retry just because the four-second message appears.

### Replay

- Identify the saved question and profile first.
- Lead with `delta_breach_rate` (or baseline if delta is absent) and say exactly
  “of simulated futures fall below [threshold]”. Avoid “safe”, approval marks,
  or interpreting the result as permission to spend.
- Compare with `baseline_breach_rate` in smaller adjacent text.
- Show the request prose when available. `/run/{id}` does not currently return
  saved prose; reconstruct only deterministic factual summaries on direct
  replay loads. No extra Gemini request is needed to view a replay.
- Contributor shows its label, amount, and marginal contribution in percentage
  points. When null, show “No contributing recurring charge” and the actual
  interpretation, rather than an empty card or a guessed merchant.
- Essential obligations remain readable with a textual “Essential” label;
  never lower contrast to imply disabled data.
- Copy replay link gives polite success feedback and a selectable URL fallback
  if clipboard access is unavailable. A local prototype link is labelled as
  such; production links use the deployed frontend origin.

### Balance paths

Receive all 500 paths. Compute p10, p50, and p90 per balance index in the browser
with linear percentile interpolation. Render 20 representative paths selected
deterministically across minimum-balance rank, preserving the worst and best.
Do not ask the API to downsample or change its contract.

Show a navy median, pale-blue p10-p90 band, fine blue samples, and a dashed
threshold. Label the band “Middle 80% of simulated balances”; it is a pointwise
distribution, not an 80% guarantee about an entire trajectory. Index 0 is the
opening balance; index w is end of week w. The horizontal axis uses weeks, not
invented calendar dates. USD units and the threshold are always visible.

A labelled week range control provides keyboard/touch access to numerical
percentiles. Offer a small accessible summary table for the selected week.
Tooltips are optional enhancement, never the only way to inspect a value.
Use three x-axis labels on small screens and five on desktop.

### Model and evidence

Use the model saved with the run, not today's `/model/{customer_id}`, since a
later ingestion could change the fit. Display opening balance, income cadence,
recurring amounts, discretionary assumptions, and fit-window length.

Evidence opens as a native modal sheet on desktop and full-width sheet on
mobile. Keep its title, close button, record identity, amount, date, and
description visible. Paginate long lists. Opening moves focus into the sheet;
Escape closes it; closing restores focus to the opener.

Display raw transaction money according to `amount_units.evidence[id]` from
saved inputs or `X-Monetary-Unit` from `/txn`. Divide only explicit `usd_cents`
values by 100. Missing or unsupported unit metadata produces an unavailable
formatted amount, not a guessed unit. Model/delta/claims remain dollars.
Show the untouched original JSON in a disclosure; present unit metadata beside
it. Missing evidence is an error state, not a verified claim.

## Responsive behavior and accessibility

- At 900px, replay becomes one column: summary, chart, contributor, explanation.
- At 640px, navigation simplifies, outer gutters become 20px, form fills the
  width, comparison stacks, and action labels stay on one line.
- Mobile entry art sits behind the upper right at low contrast. It never pushes
  the question form below a large decorative hero.
- All actions are native buttons or links; all fields have persistent labels.
  Provide a skip link, visible focus outlines, logical heading levels, and
  polite status announcements. Focus must not be hidden by sticky UI.
- Touch targets are at least 44px, preferably 48px. Pinch zoom stays enabled.
- Respect reduced motion, reduced transparency, and forced colors. Information
  remains complete with images disabled. Decorative art has empty alt text.
- The design is intentionally light-only per the supplied Aero reference.
- Errors retain useful context. No hover-only feature or color-only distinction.

## Prototype and production boundary

Run from the repository root:

```sh
python3 -m http.server 4173 --bind 127.0.0.1 --directory docs/frontend/prototype
```

Open `http://127.0.0.1:4173`. The prototype is buildless HTML/CSS/JS to make this
design immediately reviewable. It is not the production Next.js frontend or a
Gemini integration. It supports two synthetic profiles, two precomputed
questions, replay, chart inspection, model details, evidence, and copied links.
Unsupported wording produces an honest prototype limitation message.

`generate_samples.py` uses the repository's real fitter and core with the
existing cached synthetic population, 500 paths, 104 weeks, seed 1337. It saves
the full results and only the evidence referenced by each model. No network
requests or bank writes are made. Generated mockups have illustrative records;
the prototype is the authoritative source for its displayed sample values.

Production implementation should use Next.js route layouts, a small client
question form, a client chart island, and an accessible evidence dialog. Keep
bank/Gemini credentials on the API side. Configure the deployed API origin
server-side and preserve the existing Python contracts. No deployment is part
of this design pass.

## References

- User-supplied [Frutiger Aero](../../frutiger-aero-design.md) and
  [image-to-code](../../image-to-code.md).
- Installed [Leonxlnx taste skill](../../.agents/skills/design-taste-frontend/SKILL.md).
- [Vercel Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md), retrieved October 10, 2026.
- [UNC Kenan-Flagler branding guide, digital color palette](https://www.kenan-flagler.unc.edu/wp-content/uploads/2025/02/KFBS25-005_Brand_Guide_Update_2024_FNL_Digital_revised_2.pdf).
- [Architecture](../../00-ARCHITECTURE.md), [full-path chart handshake](../../core/HANDSHAKE_NOTES.md),
  [money units](../MONEY_UNITS.md), and [seed verification](../seed-verification.json).

All screen references and the water asset were generated for this project.
They depict an imagined landscape, not the UNC campus. The theme uses Carolina
colors without implying university affiliation.
