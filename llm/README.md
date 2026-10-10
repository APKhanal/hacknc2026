# LLM Layer: Gemini Claims Validator

This package implements the DEV C specification: a Gemini-powered system that translates at the boundaries of a deterministic spending analysis system, with a centerpiece validator that ensures the model never writes a number that isn't in a claim.

## Architecture

```
parse() → DecisionDelta
  ↓
render() → prose (with validation)
  ↓
validate() ← claims only
  ↓
answer() → fallback to template
```

## Core Principle

**Gemini is a translator at two boundaries, not the system itself.**

1. **Input boundary:** Parse raw text into structured decisions
2. **Output boundary:** Render typed claims into natural prose
3. **Validation:** Reject any prose containing numbers that aren't traceable to claims

## Modules

### `models.py`
Type definitions for the data flowing through the system:
- `DecisionDelta`: parsed text message
- `Claim`: typed claim from simulation (amount, kind, evidence IDs)
- `Culprit`: identified merchant/category
- `ValidationResult`: validation result with violations

### `template.py`
Deterministic fallback for prose generation. **Build this first.** It unblocks B's `/ask` endpoint immediately and provides a safety net for Saturday afternoon.

Requirements:
- Always works (no exceptions)
- Handles unknown claim kinds gracefully
- Output passes the validator
- Returns same structure as render (per Blocker 1)

### `parse.py`
Parse inbound text into `DecisionDelta` using Gemini (or heuristic fallback).

Key behaviors:
- **Always receives today's date explicitly** — model never guesses what today is
- Confidence is calibrated, not vibes:
  - ≥ 0.85: explicit amount + unambiguous kind
  - 0.5–0.85: amount present but timing/kind needs default
  - < 0.5: no amount, conflicting amounts, or not a spending decision
- Post-model guards reject invented amounts and empty values
- Falls back to heuristic parsing if Gemini unavailable

### `validate.py`
The centerpiece. Three non-negotiable checks, all violations collected:

1. **Numeric trace:** Every number regex'd from prose must match a claim value (with tolerance)
2. **Evidence existence:** Every transaction ID must resolve via `/txn/`
3. **Culprit consistency:** Merchant named must match what simulation found

Tolerances:
- Integers: exact match
- Dollars: 2 decimal places (`$142` == `142.00`)
- Probabilities: 1 percentage point (`0.27` matches "27%")
- Hedge words next to numbers: violation

### `render.py`
Render claims to prose using Gemini.

Type signature enforces isolation:
```python
def render(claims: list[Claim], culprit: Culprit) -> str
```

Never receives `SimResult`, transaction records, or raw model output. The type signature itself is the enforcement mechanism; no `**kwargs` escape hatch.

Critical prompt rules:
- Every number comes from `claim.value`, verbatim
- No computed, rounded, averaged, or inferred figures
- No hedge words next to numbers
- Probabilities formatted as whole-percent: `0.27` → "27%"
- 3–5 sentences, iMessage-appropriate
- **Lead with probability, name culprit, end with replay link reference**

### `answer.py`
Orchestration entry point for B and D.

Flow:
1. `render(claims, culprit)`
2. `validate(prose, claims, culprit)` → if passed, return prose
3. Retry `render()` once with violations as feedback
4. Validate again → if passed, return prose
5. Fall back to `template(claims, culprit)`

**Path logging:** Tracks which path served each response (`render_first_try`, `render_retry`, `template`). Counter shows judges that Gemini actually fires in the demo.

```python
stats = get_path_stats()
# {"render_first_try": 42, "render_retry": 3, "template": 5}
```

### `scripts/check_evidence.py`
One-shot utility for Blocker 3. Checks if transaction IDs resolve.

```bash
python llm/scripts/check_evidence.py txn_001 txn_002 txn_003
# or
cat evidence_ids.txt | python llm/scripts/check_evidence.py
```

Output shows which IDs exist and which are 404.

## Testing

Run all tests:
```bash
pytest llm/tests/ -v
```

By category:
```bash
pytest llm/tests/test_template.py -v   # Fallback rendering
pytest llm/tests/test_parse.py -v      # Text parsing
pytest llm/tests/test_validate.py -v   # Validation checks
pytest llm/tests/test_answer.py -v     # Orchestration
```

### Key Test Suites

- **test_template.py:** Template renders all claim kinds; unknown kinds skipped; output passes validator
- **test_parse.py:** 10 required phrasings; confidence calibration; graceful degradation
- **test_validate.py:** 
  - Numeric trace: currency formats, percentages, k suffix, negative amounts, orphan detection
  - Evidence existence: 200, 404, timeout
  - Culprit consistency: present, missing, case-insensitive
  - Adversarial: hand-written prose with plausible fabricated numbers
- **test_answer.py:** Never raises; path stats tracked; fallback works

### Adversarial Test (Live Demo)

```bash
pytest llm/tests/test_validate.py::TestAdversarial -v -s
```

This is what you run on stage. It feeds the validator a prose string with a plausible but fabricated number and asserts it rejects. Clean output, highlighted violation, then validated version passing.

## Environment

```bash
export GEMINI_API_KEY="your-api-key"
```

The key is loaded from the environment at runtime, never committed or logged.

## Blockers and Coordination

### Blocker 1 — Friday 7:00 PM (Dev D)
**What you need:** Message format constraints (length budget, bubble splitting, return shape)

**Say:** "What's your length budget per bubble? Inline replay link or separate message? Single string or list[str] for pacing?"

**Update:** Modify `template()` and `render()` return type after agreement.

### Blocker 2 — Saturday 9:00 AM (Dev A)
**What you need:** Real claim list + agreed vocabulary for `kind` field

**Say:** "Here's a claim list. These two numbers I want to say—can you add those kinds?"

**Update:** Test `render()` against real claims; update validation logic if new kinds appear.

### Blocker 3 — Saturday 11:00 AM (Dev B)
**What you need:** Zero 404s on evidence IDs

**Say:** "50 evidence IDs from your model. Running existence check now."

**Script:** `python llm/scripts/check_evidence.py [ids...]`

## Definition of Done

- [x] `template.py` — deterministic fallback, always works
- [x] `parse.py` — handles one_time, recurring, ambiguous with calibrated confidence
- [x] `render.py` — receives claims only, enforced by type signature
- [x] `validate.py` — rejects orphan numbers, unresolvable IDs, culprit mismatches
- [x] `answer.py` — retry-once-then-template, never raises, path counter
- [x] Tests — 40+ cases covering all three validation checks + adversarial
- [x] Evidence script — ready for Blocker 3
- [ ] Blocker 1 coordination — return shape agreed with Dev D
- [ ] Blocker 2 coordination — real claims tested with Dev A
- [ ] Blocker 3 coordination — zero 404s with Dev B

## Failure Modes to Avoid

**Raw SimResult in render:** The moment the model sees `paths` array, it computes its own numbers. Claims only. Type signature enforces it.

**Template before render:** ✓ Done. Unblocks B and saves you Saturday.

**Validator too strict:** Watch for `0.27` vs "27%", `$142` vs "142.00". Normalize properly. **Default: never hedge, no tolerance.**

**Silent template fallback:** If validator rejects everything, demo "works" but Gemini never speaks. Watch path counter; treat > 20% template rate on real claims as a bug.

**Tuning prompt before Blocker 1:** Blocker 1 prevents this. Know D's format first.

**Trusting parser math:** Recompute `start_day` in Python, verify amount in text. Parser held to same standard as render: no invented numbers.

## Next Steps

1. Ship `template()` to B by Fri 3 PM (unblocks `/ask`)
2. Test `parse()` on 10 phrasings (Fri 3–5 PM)
3. Build validator Check 1: numeric trace (Fri 5–7 PM)
4. Coordinate with D on format (Fri 7 PM)
5. Build `render()` and tune prompt (Fri 7:30–10 PM)
6. Build `answer()` orchestration (Fri 10–11:30 PM)
7. Adversarial test, make it projector-clean (Sat 8–9 AM)
8. Coordinate with A on real claims (Sat 9 AM)
9. Coordinate with B on evidence (Sat 11 AM)

By Sat 12 PM: hard gate. All validators pass, path counter shows Gemini firing, demo ready.
