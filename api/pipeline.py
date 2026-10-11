"""Integration seams for Dev C; no Gemini prompts or SDK calls live here."""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from core.model import Claim, DecisionDelta, SimResult
from core.run import run
from data.demo import TEST_TRIGGER_CUSTOMERS


class RephraseRequired(ValueError):
    pass


RENDER_CACHE_PATH = Path(__file__).resolve().parent.parent / "llm" / "render_cache.json"


def claims_cache_key(claims: list[Claim]) -> str:
    """Stable hash of (kind, value, unit) across claims, order-independent.

    Sorted by kind (always unique within one SimResult.claims, per the
    frozen vocabulary) so the sort itself never needs to compare value,
    which is `float | str` and not orderable across claims.
    """
    ordered = sorted(claims, key=lambda c: c.kind)
    normalized = [[c.kind, c.value, c.unit] for c in ordered]
    # Old cached paragraphs predate the readable response format.
    blob = json.dumps({"copy_version": 4, "claims": normalized}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def _load_render_cache() -> dict:
    try:
        return json.loads(RENDER_CACHE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_cached_render(cache_key: str) -> str | None:
    return _load_render_cache().get(cache_key)


def save_cached_render(cache_key: str, prose: str) -> None:
    cache = _load_render_cache()
    cache[cache_key] = prose
    RENDER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RENDER_CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def explicit_parse(text: str) -> DecisionDelta:
    """Offline unblocking fake: only accepts complete, explicit forms, never guesses dates."""
    pattern = (
        r"(?:can i afford|spend)\s+\$(?P<amount>\d+(?:,\d{3})*(?:\.\d{1,2})?)"
        r"(?P<cadence>/(?:month|mo|week|year))?\s+"
        r"(?:starting\s+)?(?P<date>today|in (?P<days>\d+) days)\??"
    )
    match = re.fullmatch(pattern, text.strip(), re.IGNORECASE)
    if not match:
        raise RephraseRequired("Please include an amount and timing, for example: Can I afford $1400 today? "
                               "Offline mode also supports $65/month starting today or in 30 days.")
    cadence = {"/month": 30, "/mo": 30, "/week": 7, "/year": 365}.get((match["cadence"] or "").lower())
    return DecisionDelta(kind="recurring" if cadence else "one_time",
                         amount=float(match["amount"].replace(",", "")),
                         start_day=int(match["days"] or 0), cadence_days=cadence,
                         label="Explicit expense", raw_text=text, confidence=1.0)


def parse(text: str, mode: str = "auto") -> DecisionDelta:
    if mode == "explicit":
        return explicit_parse(text)
    try:
        module = importlib.import_module("llm.parse")
    except ModuleNotFoundError as exc:
        if mode == "auto" and exc.name in ("llm", "llm.parse"):
            return explicit_parse(text)
        raise RephraseRequired("The decision parser is unavailable. Please try again when it is configured.") from None
    # Parsing never calls Gemini, regardless of whether google-genai
    # is importable or a key is present: the heuristic parser is correct and
    # free, and routing parse through Gemini is what previously burned quota
    # and, on a dead key, swallowed past this fallback into a zeroed delta.
    return module._parse_heuristic(text, date.today())


def render(claims, culprit):
    return importlib.import_module("llm.render").render(claims, culprit)


def fake_gemini_render(claims, culprit):
    """Deterministic, network-free renderer: the test1-5 trigger's prose
    source, and a fast/realistic stand-in for `render` in tests."""
    return importlib.import_module("llm.render").fake_gemini_render(claims, culprit)


def validate(prose, claims, culprit=None):
    """Validate prose against claims. Culprit is required for full validation."""
    return importlib.import_module("llm.validate").validate(prose, claims, culprit, txn_resolver=None)


def test_fixture_customer(text: str) -> str | None:
    """customer_id to use for a test-trigger request, or None if text isn't one.

    Strips everything but letters/digits before matching: phone autocorrect
    reliably mangles a bare "test1" into "Test 1" (inserted space) or "test1."
    (trailing period) on send, and an exact-match lookup would silently miss
    both, falling through to the real parser and surfacing a confusing
    "parsing was unavailable" error on what the user typed as a trigger.
    """
    normalized = re.sub(r"[^a-z0-9]", "", text.strip().lower())
    return TEST_TRIGGER_CUSTOMERS.get(normalized)


def test_fixture_delta(text: str) -> DecisionDelta:
    """Fixed decision for test-trigger requests.

    Deliberately the same decision "Can I afford $1400 today?" already
    produces via explicit_parse - test_each_fixture_can_be_asked_without_network
    already proves this succeeds end-to-end against all 5 demo_* profiles,
    so this is the lowest-risk choice rather than a new untested scenario.
    """
    return DecisionDelta(kind="one_time", amount=1400.0, start_day=0,
                         label="Test fixture expense", raw_text=text, confidence=1.0)


def validate_delta(delta: DecisionDelta | dict) -> DecisionDelta:
    if isinstance(delta, dict):
        delta = DecisionDelta.from_dict(delta)
    if not isinstance(delta, DecisionDelta):
        raise RephraseRequired("Please rephrase with a specific amount and date.")
    if delta.amount is None:
        raise RephraseRequired("Please include a dollar amount, like \"Can I afford $400 today?\"")
    if delta.start_day is None or delta.confidence is None:
        raise RephraseRequired("Please rephrase with a positive amount and a clear date or recurrence.")
    numbers =(delta.amount, delta.start_day, delta.confidence)
    if (not all(math.isfinite(x) for x in numbers) or delta.amount <= 0 or delta.start_day < 0
            or not 0.5 <= delta.confidence <= 1
            or (delta.cadence_days is not None and (not math.isfinite(delta.cadence_days) or delta.cadence_days <= 0))):
        raise RephraseRequired("Please rephrase with a positive amount and a clear date or recurrence.")
    if delta.kind == "one_time" and delta.cadence_days is not None:
        raise RephraseRequired("Please clarify whether this is a one-time or recurring expense.")
    return delta


def template(claims: list[Claim]) -> str:
    """Numbers and merchant names are formatted directly from typed claim values.

    Only explains the driver; readable_response adds the verdict and odds.
    """
    values = {claim.kind: claim.value for claim in claims}
    if "culprit_label" in values:
        return (f"Your biggest recurring pressure is {values['culprit_label']} "
                f"at {_money(float(values['culprit_amount']))} per payment. "
                "The replay shows how much it matters.")
    return "No single recurring bill is driving this."


def _money(value: float) -> str:
    return f"${value:,.0f}" if float(value).is_integer() else f"${value:,.2f}"


def _odds(rate: float) -> str:
    if 0 < rate < 0.01:
        return "under 1%"
    if 0.99 < rate < 1:
        return "over 99%"
    return f"{math.floor(rate * 100 + 0.5)}%"  # halves up, like the web's Math.round


def _when(day: date, today: date) -> str:
    offset = (day - today).days
    if offset == 0:
        return "today"
    if offset == 1:
        return "tomorrow"
    label = f"{day.strftime('%b')} {day.day}"
    return f"on {label}" if day.year == today.year else f"on {label}, {day.year}"


def _cadence(days: float) -> str:
    return {1: "a day", 7: "a week", 14: "every two weeks", 30: "a month",
            365: "a year"}.get(days, f"every {days:g} days")


def _horizon(weeks: int) -> str:
    if weeks % 52 == 0:
        years = weeks // 52
        return "year" if years == 1 else f"{years} years"
    return f"{weeks} weeks"


# A recurring charge must move the odds by at least this much to be called out.
# Mirrored in web/lib/summary.ts.
CULPRIT_MIN_CONTRIBUTION = 0.05


def dip_summary(result: SimResult) -> dict | None:
    """When, how deep and how long the typical shortfall is, across paths that have one."""
    dipped = [p for p in result.paths if p.first_breach_week is not None]
    if not dipped:
        return None
    first = sorted(p.first_breach_week for p in dipped)[len(dipped) // 2]
    below = sorted(sum(b < result.breach_threshold for b in p.balances[1:]) for p in dipped)[len(dipped) // 2]
    final = sorted(p.balances[-1] for p in result.paths)[len(result.paths) // 2]
    return {"share": len(dipped) / len(result.paths), "first_week": first,
            "weeks_below": below, "recovers": final > result.breach_threshold}


def _dip_line(result: SimResult, today: date) -> str:
    dip = dip_summary(result)
    if dip is None or float(result.delta_breach_rate) <= float(result.baseline_breach_rate):
        return ""
    week_of = today + timedelta(weeks=dip["first_week"])
    when = f"the week of {week_of.strftime('%b')} {week_of.day}"
    if dip["share"] < 0.5:
        return f"If it does go wrong, the tight spot is most likely {when}."
    # Most paths dip here, so the all-path median low is the typical one and
    # matches the "typical lowest balance" shown on the replay and cards.
    # Rounds halves up (not Python's round-half-even) to match the web's Math.round.
    depth = abs(result.median_min_balance - result.breach_threshold)
    weeks = dip["weeks_below"]
    span = "about a week" if weeks <= 1 else f"about {weeks} weeks"
    line = (f"Most likely you'd drop below {_money(result.breach_threshold)} {when}, "
            f"bottom out around ${math.floor(depth + 0.5):,} short, and stay there for {span}")
    return line + (" before your paychecks catch up." if dip["recovers"] else ".")


def readable_response(result: SimResult, delta: DecisionDelta, prose: str, today: date) -> str:
    """Add context directly from checked simulation outputs and parsed inputs.

    Keep this outside the LLM and its claims-only cache: two questions can
    produce identical claims while having different amounts or payment dates.
    """
    rate = float(result.delta_breach_rate)
    base = float(result.baseline_breach_rate)
    when = _when(today + timedelta(days=delta.start_day), today)
    if delta.kind == "recurring":
        starting = "starting today" if when == "today" else f"starting {when.removeprefix('on ')}"
        what = f"adding {_money(delta.amount)} {_cadence(delta.cadence_days)} {starting}"
    else:
        what = f"spending {_money(delta.amount)} {when}"
    what = what[0].upper() + what[1:]

    # Tiers match web/lib/verdict.ts (Sustainable < 20%, Worth a look < 50%).
    if rate == 0:
        lead = f"{what} looks safe. Your balance stayed above {_money(result.breach_threshold)} in every simulation."
    elif rate <= base:
        lead = ("Your cash is already tight, with or without this."
                if base >= 0.5 else f"{what} doesn't really change your odds.")
    elif rate < 0.2:
        lead = f"{what} looks manageable."
    elif rate < 0.5:
        lead = f"{what} is doable, but worth a second look."
    else:
        lead = f"Heads up: {what[0].lower() + what[1:]} would be a real stretch."

    odds = (f"Chance your balance dips below {_money(result.breach_threshold)} "
            f"in the next {_horizon(result.horizon_weeks)}:\n"
            f"With it: {_odds(rate)}\n"
            f"Without it: {_odds(base)}")
    footer = f"This is a forecast from {result.n_paths} simulations, not a guarantee."
    # A contributor that barely moves the odds is noise next to the verdict.
    if result.culprit is None or result.culprit.marginal_contribution < CULPRIT_MIN_CONTRIBUTION:
        prose = ""
    parts = [lead, _dip_line(result, today), odds, prose.strip(), footer]
    return "\n\n".join(part for part in parts if part)


def check_evidence(result: SimResult, resolve: Callable) -> None:
    if not result.claims:
        raise ValueError("Simulation emitted no evidenced claims")
    for claim in result.claims:
        if not claim.evidence:
            raise ValueError("Claim has no transaction evidence")
        for tid in claim.evidence:
            resolve(tid)


def checked_template(result: SimResult) -> str:
    """Fallback validation is construction-based; arbitrary prose never enters it."""
    values = {claim.kind: claim for claim in result.claims}
    expected = {"baseline_breach_rate": result.baseline_breach_rate,
                "breach_rate_with_delta": result.delta_breach_rate,
                "paths_simulated": result.n_paths}
    if result.culprit:
        expected.update(culprit_label=result.culprit.label, culprit_amount=result.culprit.amount,
                        culprit_marginal_contribution=result.culprit.marginal_contribution)
    elif "culprit_label" in values:
        raise ValueError("Unexpected culprit claim")
    for kind, value in expected.items():
        if kind not in values or values[kind].value != value:
            raise ValueError("Claim/result mismatch")
        if isinstance(value, (int, float)) and not math.isfinite(value):
            raise ValueError("Non-finite claim")
    return template(result.claims)


def validation_passed(value) -> bool:
    return (value.get("passed") if isinstance(value, dict) else getattr(value, "passed", None)) is True


@dataclass
class Pipeline:
    parser: Callable
    renderer: Callable = render
    validator: Callable = validate
    simulator: Callable = run
