# Design verification

Checked October 10, 2026. This verifies the local design prototype, not the
deployed API, Gemini, Photon, or a production Next.js implementation.

## Browser checks

Chrome desktop at 1366 × 768, mobile at 390 × 844, and narrow mobile at
320 × 740 were inspected. Entry, replay, and model views rendered. The entry
submit button ends at 604px on the 768px desktop viewport. Replay document
width matches viewport width at 1366px, 390px, and 320px after correcting the
narrow percentile readout.

Verified interactions:

- Submit Alex's $1,400 example and see 4.0% with Geico as contributor.
- Select Drew and the gym example; see 0.0% and the no-contributor state.
- Unsupported question preserves input, shows an inline explanation, and
  focuses the question field.
- Model tab shows the saved opening balance and recurring obligations.
- Keyboard arrow changes the chart week and its accessible numerical summary.
- Evidence opens in a modal, focuses Close, paginates, and returns focus to its
  opener after Escape/Close.
- Transaction dates are ordered newest first and cents display as dollars.
- Copy replay link shows success feedback.
- No JavaScript error or warning entries were returned from the browser log
  during the inspected flow.

Screenshots: [desktop entry](screenshots/entry-desktop.png),
[desktop replay](screenshots/replay-desktop.png),
[mobile replay](screenshots/replay-mobile.png).

## Numerical and source checks

- All four samples contain 500 paths and 105 balance observations per path.
- Counts of paths with first breaches match the displayed breach rates.
- All 1,260 p10/p50/p90 values computed by the browser module match NumPy's
  percentiles within numerical tolerance.
- The selected 20 unique sample paths preserve the worst and best path by
  minimum balance. Percentiles use every path, not just displayed samples.
- Unit conversion distinguishes dollars and explicit cents. Unknown units
  return unavailable values.
- JavaScript syntax checks pass. No external runtime dependencies are required.

Measured color pairs:

| Foreground / background | Contrast |
| --- | ---: |
| Navy / darkest primary-button stop | 6.82:1 |
| Secondary ink / white | 6.77:1 |
| Link blue / white | 6.53:1 |
| Navy / white | 14.52:1 |
| Secondary ink / mist | 6.12:1 |

## Web Interface Guidelines review

Applied the installed web-design-guidelines skill and its fetched source rules
to `prototype/index.html`, `styles.css`, `app.js`, and `chart-data.mjs`.
Checked semantic controls, labels, visible focus, status announcements, modal
focus return, text wrapping, image sizing strategy, reduced-motion styling,
native input behavior, stateful URLs, and locale-based money formatting.

Corrected during review: narrow-screen header controls, 320px numerical-row
overflow, long record descriptions, distinguishable evidence button names,
explicit copy-button accessible name, and singular percentage-point wording.

Limitations: this was a manual browser and code review, not an accessibility
certification. Screen-reader speech, forced-color rendering, clipboard-denied
fallback, slow-network states, and an automated Lighthouse run were not tested.
No production performance or `/ask` latency claims are made. Reduced-motion and
reduced-transparency fallbacks are implemented but were not toggled in the
browser. The example-question restrictions are intentional prototype scope.
