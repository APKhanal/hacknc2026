"""Integration seams for Dev C; no Gemini prompts or SDK calls live here."""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date
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
    blob = json.dumps(normalized, sort_keys=True)
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
    # Parsing never calls Gemini, regardless of whether google-generativeai
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
    """customer_id to use for a test-trigger request, or None if text isn't one."""
    return TEST_TRIGGER_CUSTOMERS.get(text.strip().lower())


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
    numbers = (delta.amount, delta.start_day, delta.confidence)
    if (not all(math.isfinite(x) for x in numbers) or delta.amount <= 0 or delta.start_day < 0
            or not 0.5 <= delta.confidence <= 1
            or (delta.cadence_days is not None and (not math.isfinite(delta.cadence_days) or delta.cadence_days <= 0))):
        raise RephraseRequired("Please rephrase with a positive amount and a clear date or recurrence.")
    if delta.kind == "one_time" and delta.cadence_days is not None:
        raise RephraseRequired("Please clarify whether this is a one-time or recurring expense.")
    return delta


def template(claims: list[Claim]) -> str:
    """Numbers and merchant names are formatted directly from typed claim values."""
    values = {claim.kind: claim.value for claim in claims}
    probability = float(values["breach_rate_with_delta"])
    baseline = float(values["baseline_breach_rate"])
    count = int(values["paths_simulated"])
    prose = (f"In {count} simulated futures, the chance of a balance below the breach threshold "
             f"with this expense is {probability:.2%}, compared with {baseline:.2%} without it.")
    if "culprit_label" in values:
        prose += (f" The largest contributing recurring charge selected by the simulation is "
                  f"{values['culprit_label']} (${float(values['culprit_amount']):.2f}); removing it reduces "
                  f"the breach rate by {float(values['culprit_marginal_contribution']) * 100:.2f} percentage points.")
    else:
        prose += " No recurring charge had a positive measured contribution to the breach rate."
    return prose + " See the replay for paths and transaction evidence."


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
