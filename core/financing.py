"""If paying up front is too risky, which loan term would keep the user above zero?"""
from __future__ import annotations

from dataclasses import dataclass, replace

from core.feasible import SAFE_BREACH_RATE, _is_fixed
from core.loans import DAYS_PER_MONTH, monthly_payment
from core.model import CashflowModel, Decision, DecisionDelta, as_decision
from core.rates import DEFAULT_RATES, TERM_OPTIONS_MONTHS
from core.simulate import delta_outflow, flow_components, make_noise, paths_from_components

MIN_FINANCED_AMOUNT = 500.0


@dataclass(frozen=True)
class FinancingOption:
    label: str  # the purchase being financed
    amount: float
    apr: float
    months: int
    monthly_payment: float
    total_interest: float
    breach_rate: float


@dataclass(frozen=True)
class FinancingResult:
    label: str
    amount: float
    apr: float
    option: FinancingOption | None  # shortest term that is safe, None when no listed term is


def financeable_index(decision: Decision) -> int | None:
    """The biggest up-front outflow (a purchase or a down payment) not already a loan's proceeds."""
    best = None
    for i, it in enumerate(decision.items):
        if it.kind == "one_time" and it.direction == "outflow" and not _is_fixed(it) and it.amount >= MIN_FINANCED_AMOUNT:
            if best is None or it.amount > decision.items[best].amount:
                best = i
    return best


def _financed(decision: Decision, index: int, apr: float, months: int) -> tuple[Decision, float]:
    item = decision.items[index]
    payment = round(monthly_payment(item.amount, apr, months / 12), 2)
    pay_item = DecisionDelta(kind="recurring", amount=payment, start_day=item.start_day, cadence_days=DAYS_PER_MONTH,
                             end_day=item.start_day + months * DAYS_PER_MONTH, label=f"{item.label} financing",
                             raw_text=item.raw_text, confidence=item.confidence)
    items = tuple(pay_item if i == index else it for i, it in enumerate(decision.items))
    return replace(decision, items=items), payment


def financing_options(
    model: CashflowModel,
    decision: Decision | DecisionDelta,
    rates: dict[str, float] | None = None,
    seed: int = 1337,
    n_paths: int = 500,
    horizon_weeks: int = 104,
    safe_rate: float = SAFE_BREACH_RATE,
    breach_threshold: float = 0.0,
) -> FinancingResult | None:
    """Shortest listed term at which financing the main up-front cost keeps the odds at or under safe_rate.

    Uses the same seed and horizon as the main run, so the odds are comparable with the ones shown.
    """
    decision = as_decision(decision)
    index = financeable_index(decision)
    if index is None:
        return None
    apr = float({**DEFAULT_RATES, **(rates or {})}["personal"])
    item = decision.items[index]
    noise = make_noise(seed, n_paths, horizon_weeks, len(model.recurring))
    comp = flow_components(model, None, noise)
    for months in TERM_OPTIONS_MONTHS:
        financed, payment = _financed(decision, index, apr, months)
        paths = paths_from_components(replace(comp, delta=delta_outflow(financed, horizon_weeks)), breach_threshold)
        rate = paths.breach_rate
        if rate <= safe_rate:
            return FinancingResult(item.label, item.amount, apr, FinancingOption(
                item.label, item.amount, apr, months, payment, round(payment * months - item.amount, 2), round(rate, 4)))
    return FinancingResult(item.label, item.amount, apr, None)
