# Demo Polish — Idea Backlog

Ideas for making the live demo more impressive, beyond what's already built
(chart + stats image cards, the test1–test5 no-Gemini trigger path, the
validator's adversarial pytest). Not all of these are scheduled — this is a
holding pen so nothing gets lost. Status noted per item.

---

## 1. QR code on a card

**Status: Deferred — not useful until deployed.**

Embed a QR code (linking to the replay URL) on the stats or chart PNG card,
so judges/audience can scan it with their own phone and pull up the
interactive replay instantly instead of typing a URL.

**Why deferred:** right now `REPLAY_BASE_URL` points at `localhost`, which
only resolves on the machine running the frontend — a QR code encoding that
URL would be unscannable/unreachable from anyone else's phone. Worth
revisiting once there's a real deployed (or tunneled) frontend origin.

**When picked back up:** a small QR-encoding library (no network dependency —
generate client-side or server-side from the already-known `replay_url`),
rendered as a third image card or embedded into an existing one. Low effort
once the URL problem is solved.

---

## 2. Live "validator catches a fabrication" trigger through Photon

**Status: Backlog — strong demo value, not yet built.**

The project's core pitch is "Gemini never writes a number," proven today only
by a pytest adversarial test (`llm/tests/test_validate.py` or similar —
feeds the validator a hand-written prose string with a plausible but
fabricated figure and asserts rejection). The architecture doc's own demo
script (step 6) calls for showing this live, but there's no way to trigger it
through the actual running system yet — it only runs in CI/test output.

**The idea:** a special text trigger (parallel to `test1`–`test5`, e.g.
`testvalidator`) that, when texted to the agent, deliberately constructs a
prose string containing a fabricated number against a real claim set, runs it
through the real `llm.validate.validate()`, and replies showing the
rejection live — e.g. "Gemini tried to say: '...$11.99...' → REJECTED:
orphan number '$11.99' matches no claim. Here's the validated version
instead: [real template/fake_gemini_render output]." Makes the thesis
directly demonstrable via a real text message on stage, not just described
or shown in a terminal.

**Rough shape:**
- `api/pipeline.py`: a `fabricate_bad_prose(claims, culprit)` helper that
  takes real claims and injects one plausible-but-wrong number
- Wire into the `COUNTERFACTUAL_TEST_TRIGGERS` map (or a new env-gated map)
  alongside `test1`–`test5`, reusing the same synthetic-profile-driven
  simulation so the claims are real
- Response prose explicitly narrates both the rejected attempt and the
  validated fallback, so it reads clearly over iMessage

---

## 3. Color-coded verdict badge on the stats card

**Status: Building now.**

A small badge (icon + color + text label — never color alone, per
accessibility guidance) next to the headline breach-rate stat, using the
same sustainable / worth-a-look / real-stretch classification already in
`llm/render.py`'s `fake_gemini_render`. Applied to both the static stats PNG
card (`web/components/workspace/export-cards.tsx`) and the interactive
replay page (`web/components/workspace/replay-result.tsx`), sharing one
classification utility so the phone reply and the big-screen replay agree.

Colors from the dataviz skill's validated status palette: good `#0ca30c`,
warning `#fab219`, critical `#d03b3b`.

---

## 4. Overlay baseline-vs-decision bands on one chart

**Status: Built.**

`SimResult` now carries `baseline_band: WeeklyBand[]` (always populated;
equal to the decision band when no delta was given). The chart draws it as a
dashed orange outline (dataviz skill categorical slot 2, `#eb6834`) behind
the solid blue decision band, with a legend, on both the chart PNG card and
the interactive replay page — whenever a decision was actually applied
(`delta_breach_rate !== null`). The interactive page's week-inspector table
also gained a baseline comparison row.

Chose the lighter option from the original two: precomputed baseline weekly
percentile bands (what actually got built), not full baseline `paths` —
cheaper, and all the chart needed. `core/run.py` already computed the full
baseline path set internally for `baseline_breach_rate`; this just stops
discarding it before constructing `SimResult`, additively (no existing field
touched, so nothing else consuming `SimResult` JSON needed to change).
