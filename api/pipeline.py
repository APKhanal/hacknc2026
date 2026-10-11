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

from core.feasible import Outlook
from core.financing import FinancingResult
from core.model import Claim, Decision, DecisionDelta, SimResult, as_decision
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


def parse(text: str, mode: str = "auto") -> DecisionDelta | Decision:
    if mode == "explicit":
        return explicit_parse(text)
    # Anything beyond one plain expense (income, loans, several amounts, rates, terms) goes to the
    # complex parser, which refuses rather than silently dropping a number.
    try:
        complex_parser = importlib.import_module("llm.parse_complex")
    except ModuleNotFoundError:
        complex_parser = None
    if complex_parser is not None and complex_parser.needs_complex(text):
        try:
            return complex_parser.parse_complex(text, date.today())
        except complex_parser.ComplexParseError as exc:
            raise RephraseRequired(str(exc)) from None
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


def validate_decision(decision: Decision | DecisionDelta | dict) -> Decision:
    """Validate every item of a (possibly multi-item) decision; a lone delta becomes a one-item decision."""
    if isinstance(decision, dict):
        decision = Decision.from_dict(decision)
    if isinstance(decision, DecisionDelta):
        return Decision.single(validate_delta(decision))
    if not isinstance(decision, Decision) or not 1 <= len(decision.items) <= 8:
        raise RephraseRequired("Please rephrase with a specific amount and date.")
    if not math.isfinite(decision.confidence) or not 0.5 <= decision.confidence <= 1:
        raise RephraseRequired("Please rephrase with a positive amount and a clear date or recurrence.")
    for item in decision.items:
        if item.end_day is not None and not math.isfinite(item.end_day):
            raise RephraseRequired("Please rephrase with a positive amount and a clear date or recurrence.")
        validate_delta(item)
    for loan in decision.terms.get("loans", []):
        if not ((loan["annual_rate"] is None or 0 <= loan["annual_rate"] <= 0.6)
                and 0 < loan["years"] <= 50 and 0 <= loan["down_payment"] < loan["price"]):
            raise RephraseRequired("Those loan terms don't look right. Please check the rate, term and down payment.")
    return decision


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


def _money_per_month(item: DecisionDelta) -> float:
    return item.amount * (365 / 12) / item.cadence_days


def _term(years: float) -> str:
    months = round(years * 12)
    if months % 12 == 0:
        n = months // 12
        return "1 year" if n == 1 else f"{n} years"
    return "1 month" if months == 1 else f"{months} months"


def _item_phrase(item: DecisionDelta, today: date) -> str:
    when = _when(today + timedelta(days=item.start_day), today)
    if item.kind == "recurring":
        starting = "starting today" if when == "today" else f"starting {when.removeprefix('on ')}"
        phrase = f"adding {_money(item.amount)} {_cadence(item.cadence_days)} {starting}"
        if item.end_day is not None:
            months = round((item.end_day - item.start_day) / 30)
            phrase += f" for {months} month{'s' if months != 1 else ''}"
        return phrase
    return f"spending {_money(item.amount)} {when}"


def describe_decision(decision: Decision | DecisionDelta, today: date) -> str:
    """Plain-language phrase for the whole decision. Every number comes from parsed inputs or code math."""
    decision = as_decision(decision)
    if (len(decision.items) == 1 and decision.items[0].direction == "outflow"
            and decision.items[0].end_day is None):
        phrase = _item_phrase(decision.items[0], today)
        return phrase[0].upper() + phrase[1:]
    loan_idx = {i for loan in decision.terms.get("loans", []) for i in loan["item_indexes"]}
    phrases = []
    for idx, item in enumerate(decision.items):
        if idx in loan_idx or item.amount == 0 or item.label == "Rent ends":
            continue
        if item.direction == "inflow" or item.label == "Pay change":
            more = item.direction == "inflow"
            phrases.append(f"earning about {_money(math.floor(_money_per_month(item) + 0.5))} "
                           f"{'more' if more else 'less'} a month")
        else:
            phrases.append(_item_phrase(item, today))
    for loan in decision.terms.get("loans", []):
        when = _when(today + timedelta(days=loan.get("start_day", 0)), today)
        if loan["rate_pct"] is None:  # the user gave the payment, not a rate
            text = (f"taking on a {_money(loan['principal'])} loan paying "
                    f"{_money(loan['monthly_payment'])} a month for {_term(loan['years'])}")
        else:
            text = (f"taking on a {_money(loan['principal'])} loan at {loan['rate_pct']:g}% over "
                    f"{_term(loan['years'])} (about {_money(math.floor(loan['monthly_payment'] + 0.5))} a month)")
        if loan["down_payment"] > 0:
            text += f" after {_money(loan['down_payment'])} down"
        if when != "today":
            text += f" {when}"
        phrases.append(text)
    if not phrases:
        phrases = ["making this change"]
    text = phrases[0] if len(phrases) == 1 else ", ".join(phrases[:-1]) + f", and {phrases[-1]}"
    return text[0].upper() + text[1:]


def decision_notes(decision: Decision | DecisionDelta) -> str:
    terms = as_decision(decision).terms
    notes = []
    if "income_tax_assumed" in terms.get("assumptions", []):
        notes.append(f"Pay figures assume about {round((1 - terms['net_factor']) * 100)}% goes to taxes.")
    if "rent_ends" in terms.get("assumptions", []):
        notes.append(f"Assumes your {_money(terms['rent_ended']['amount'])} rent stops once you buy. "
                     "Taxes, insurance and upkeep on the home are not included.")
    return " ".join(notes)


def _month_year(day: date) -> str:
    return f"{day.strftime('%b')} {day.year}"


def financing_line(result: FinancingResult | None) -> str:
    """A fixed-rate loan that would keep the odds safe, or an honest note that none of the listed terms does."""
    if result is None:
        return ""
    what = result.label if 0 < len(result.label) <= 30 and "?" not in result.label else "this"
    if result.option is None:
        return (f"Borrowing the {_money(result.amount)} for {what} at about {result.apr * 100:g}% APR "
                "wouldn't fix it on any term up to 5 years.")
    o = result.option
    term = f"{o.months} months" if o.months < 24 else f"{o.months // 12} years" if o.months % 12 == 0 else f"{o.months} months"
    return (f"A loan that works: borrowing the {_money(o.amount)} for {what} at a typical {o.apr * 100:g}% APR over "
            f"{term} is about {_money(round(o.monthly_payment))} a month ({_money(round(o.total_interest))} interest "
            f"in total) and keeps the odds of dipping below $0 to about {_odds(o.breach_rate)}.")


def outlook_line(outlook: Outlook | None, today: date) -> str:
    """When the same decision would be safe, from the engine's delayed-start search."""
    if outlook is None:
        return ""
    if outlook.feasible:
        when = _month_year(today + timedelta(days=outlook.first_start_day, weeks=outlook.wait_weeks))
        waited = (f"{outlook.wait_weeks} weeks" if outlook.wait_weeks < 9
                  else f"about {round(outlook.wait_weeks / 52 * 12)} months")
        return (f"A safer time: starting around {when} ({waited} later than you asked) would bring the odds of dipping below "
                f"$0 down to about {_odds(outlook.breach_rate)}.")
    years = _horizon(outlook.searched_weeks).replace("156 weeks", "3 years")
    line = f"Waiting up to {years} doesn't make this safe at your current income and spending."
    if outlook.monthly_gap:
        line += (f" After these payments you'd run about {_money(round(outlook.monthly_gap, -1))} a month short, "
                 "so it comes down to monthly income, not timing.")
    return line


def readable_response(result: SimResult, delta: Decision | DecisionDelta, prose: str, today: date,
                      outlook: Outlook | None = None, financing: FinancingResult | None = None) -> str:
    """Add context directly from checked simulation outputs and parsed inputs.

    Keep this outside the LLM and its claims-only cache: two questions can
    produce identical claims while having different amounts or payment dates.
    """
    rate = float(result.delta_breach_rate)
    base = float(result.baseline_breach_rate)
    what = describe_decision(delta, today)

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
    ended = as_decision(delta).terms.get("rent_ended", {}).get("label")  # rent stops, so it isn't the squeeze
    if (result.culprit is None or result.culprit.marginal_contribution < CULPRIT_MIN_CONTRIBUTION
            or result.culprit.label == ended):
        prose = ""
    parts = [lead, _dip_line(result, today), odds, outlook_line(outlook, today), financing_line(financing), prose.strip(), decision_notes(delta), footer]
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
