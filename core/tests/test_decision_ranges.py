"""Expected final-balance ranges for complex decisions, across starting balances of $0-$5,000.

Two independent checks, neither reusing the simulator's weekly bucketing:
  1. Exact: with the same noise, every path's final balance with the decision equals the
     no-decision final balance minus the decision's total net cash flow over the horizon.
  2. Range: the simulated median final balance sits near an analytic expectation
     (opening + income - spending - bills - average shocks - decision flows), inside the
     simulation's own p10-p90 band, and breach odds move the right way as starting cash grows.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from core.income import resolve_income_changes
from core.loans import loan_decision, monthly_payment
from core.model import Decision, DecisionDelta
from core.run import run
from data.demo import demo_snapshots
from data.fit import fit
from llm.parse_complex import parse_complex

HORIZON_WEEKS = 104
HORIZON_DAYS = HORIZON_WEEKS * 7
OPENINGS = (0.0, 1000.0, 2500.0, 5000.0)
TODAY = date(2026, 10, 10)
MEAN_SHOCK_PER_WEEK = 0.0175 * 850  # mean of SHOCK_PROB_RANGE x mean of SHOCK_MAGNITUDE_RANGE


def _models():
    return {s["customer"]["_id"]: fit(s) for s in demo_snapshots()}


MODELS = _models()
# demo_cushion starts at $16k, outside the $0-$5k range this test pins, but its flows are valid too.
PROFILES = list(MODELS)


def total_flow(decision: Decision) -> float:
    """Net money out over the horizon, by walking every payment day. Positive = out."""
    total = 0.0
    for item in decision.items:
        start = max(item.start_day, 0.0)
        if item.kind == "one_time":
            if start < HORIZON_DAYS:
                total += item.signed_amount
            continue
        stop = min(item.end_day if item.end_day is not None else HORIZON_DAYS, HORIZON_DAYS)
        t = start
        while t < stop:
            total += item.signed_amount
            t += item.cadence_days
    return total


def expected_base_change(model) -> float:
    """Analytic 2-year net change in balance with no decision (mean discipline = 1.0)."""
    income = model.income.mean * 365 / model.income.cadence_days * HORIZON_WEEKS / 52
    spending = model.discretionary.weekly_mean * HORIZON_WEEKS
    bills = sum(r.amount * 365 / r.cadence_days for r in model.recurring) * HORIZON_WEEKS / 52
    return income - spending - bills - MEAN_SHOCK_PER_WEEK * HORIZON_WEEKS


def gross_income(model) -> float:
    return model.income.mean * 365 / model.income.cadence_days * HORIZON_WEEKS / 52


def finals(result) -> np.ndarray:
    return np.array([p.balances[-1] for p in result.paths])


DECISIONS = {
    "cash_400": lambda: Decision.single(DecisionDelta(kind="one_time", amount=400, start_day=0)),
    "sub_65_monthly": lambda: Decision.single(
        DecisionDelta(kind="recurring", amount=65, start_day=0, cadence_days=30)),
    "raise_500_monthly": lambda: parse_complex("I got a $500/month raise", TODAY, use_llm=False),
    "loan_5k_1yr_6pct": lambda: parse_complex("Can I afford a $5,000 loan at 6% for 1 year?", TODAY, use_llm=False),
    "house_350k_20down_7pct_30y": lambda: parse_complex(
        "Can I afford a $350k house with 20% down at 7% over 30 years?", TODAY, use_llm=False),
    "car_plus_raise": lambda: parse_complex(
        "I got a $400/month raise and want a $28k car with $4k down at 5.5% for 5 years", TODAY, use_llm=False),
}


def test_loan_payment_matches_known_values():
    assert monthly_payment(294_000, 0.07, 30) == pytest.approx(1955.9, abs=0.5)
    assert monthly_payment(12_000, 0.0, 1) == pytest.approx(1000.0)
    loan = loan_decision(5000, 0.06, 1)
    assert loan.items[0].end_day == 360  # 12 payments, then it stops
    assert total_flow(loan) == pytest.approx(12 * loan.terms["monthly_payment"])
    assert 12 * loan.terms["monthly_payment"] - 5000 == pytest.approx(164.0, abs=1)  # total interest, 1y @ 6%


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("opening", OPENINGS)
@pytest.mark.parametrize("name", list(DECISIONS))
def test_final_balance_shift_is_exactly_the_decision_total(profile, opening, name):
    model = replace(MODELS[profile], opening_balance=opening)
    decision = DECISIONS[name]()
    with_it = finals(run(model, decision))
    without = finals(run(model, None))
    # balances are rounded to cents per week, so allow a few cents
    assert np.allclose(without - with_it, total_flow(decision), atol=0.05)


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("opening", OPENINGS)
@pytest.mark.parametrize("name", list(DECISIONS))
def test_median_final_balance_in_expected_range(profile, opening, name):
    model = replace(MODELS[profile], opening_balance=opening)
    decision = DECISIONS[name]()
    result = run(model, decision)
    f = finals(result)
    expected = opening + expected_base_change(model) - total_flow(decision)
    tolerance = 0.04 * gross_income(model) + 500
    assert abs(np.median(f) - expected) <= tolerance, (np.median(f), expected, tolerance)
    p10, p90 = np.percentile(f, [10, 90])
    assert p10 <= expected <= p90  # the intended balance falls inside the simulated spread


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("name", list(DECISIONS))
def test_breach_odds_fall_as_starting_cash_rises(profile, name):
    decision = DECISIONS[name]()
    rates = [run(replace(MODELS[profile], opening_balance=o), decision).delta_breach_rate for o in OPENINGS]
    assert all(a >= b - 1e-9 for a, b in zip(rates, rates[1:])), rates


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("opening", OPENINGS)
def test_direction_of_effect(profile, opening):
    model = replace(MODELS[profile], opening_balance=opening)
    out = run(model, DECISIONS["house_350k_20down_7pct_30y"]())
    inn = run(model, DECISIONS["raise_500_monthly"]())
    assert out.delta_breach_rate >= out.baseline_breach_rate  # spending can't lower the odds
    assert inn.delta_breach_rate <= inn.baseline_breach_rate  # a raise can't raise them


def test_house_is_a_real_stretch_on_every_demo_income():
    """$70k down plus ~$1.9k/month cannot fit a $0-$5k cushion on these paychecks."""
    for profile in PROFILES:
        for opening in OPENINGS:
            r = run(replace(MODELS[profile], opening_balance=opening), DECISIONS["house_350k_20down_7pct_30y"]())
            assert r.delta_breach_rate >= 0.99, (profile, opening, r.delta_breach_rate)


@pytest.mark.parametrize("opening", OPENINGS)
def test_new_job_is_resolved_against_the_fitted_paycheck(opening):
    model = replace(MODELS["demo_steady"], opening_balance=opening)
    decision = parse_complex("I got a new job making $90k a year", TODAY, use_llm=False)
    resolved = resolve_income_changes(decision, model)
    item = resolved.items[0]
    # $90k gross * 0.78 net = $70,200/yr vs ~$48.2k fitted -> about +$22k/yr, paid on the model's cadence
    current = model.income.mean * 365 / model.income.cadence_days
    assert item.direction == "inflow"
    assert item.amount * 365 / item.cadence_days == pytest.approx(70_200 - current, rel=0.01)
    base = finals(run(model, None))
    raised = finals(run(model, resolved))
    gain = np.median(raised - base)
    assert gain == pytest.approx(-total_flow(resolved), abs=0.05)
    assert 40_000 <= gain <= 46_000  # ~2 years of the ~$22k/yr difference
