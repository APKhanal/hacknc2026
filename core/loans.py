"""Deterministic loan / mortgage math. The LLM never supplies a computed amount."""
from __future__ import annotations

from core.model import Decision, DecisionDelta

DAYS_PER_MONTH = 30
DAYS_PER_YEAR = 365
PROCEEDS_SUFFIX = "loan proceeds"


def monthly_payment(principal: float, annual_rate: float, years: float) -> float:
    """Standard amortization payment. annual_rate is a fraction (0.07 = 7%)."""
    if principal <= 0 or years <= 0 or annual_rate < 0:
        raise ValueError("principal and years must be > 0 and rate >= 0")
    n = round(years * 12)
    if n < 1:
        raise ValueError("loan term must be at least one month")
    r = annual_rate / 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def loan_decision(
    principal: float,
    annual_rate: float | None,
    years: float,
    *,
    payment: float | None = None,
    down_payment: float = 0.0,
    start_day: float = 0.0,
    label: str = "Loan",
    raw_text: str = "",
    confidence: float = 1.0,
    proceeds_to_user: bool = False,
) -> Decision:
    """Down payment (one-time) plus a monthly payment that ends when the loan does.

    `proceeds_to_user` adds the borrowed cash as an inflow at the start (a personal loan; a mortgage's money
    goes to the seller, so it nets to zero). `principal` is the amount financed (price minus down payment for a mortgage). Pass `payment`
    (and annual_rate=None) when the user states the payment instead of a rate.
    """
    months = round(years * 12)
    if payment is None:
        payment = round(monthly_payment(principal, annual_rate, years), 2)
    elif not payment > 0 or payment * months < principal - 0.01:
        raise ValueError("monthly payments would not even repay the loan")
    items: list[DecisionDelta] = []
    if proceeds_to_user:
        items.append(DecisionDelta(kind="one_time", amount=float(principal), start_day=start_day, direction="inflow",
                                   label=f"{label} {PROCEEDS_SUFFIX}", raw_text=raw_text, confidence=confidence))
    if down_payment > 0:
        items.append(DecisionDelta(kind="one_time", amount=float(down_payment), start_day=start_day,
                                   label=f"{label} down payment", raw_text=raw_text, confidence=confidence))
    items.append(DecisionDelta(kind="recurring", amount=payment, start_day=start_day,
                               cadence_days=DAYS_PER_MONTH, end_day=start_day + months * DAYS_PER_MONTH,
                               label=f"{label} payment", raw_text=raw_text, confidence=confidence))
    terms = {"principal": float(principal), "annual_rate": None if annual_rate is None else float(annual_rate), "years": float(years),
             "monthly_payment": payment, "down_payment": float(down_payment), "months": months, "proceeds_to_user": proceeds_to_user}
    return Decision(items=tuple(items), label=label, raw_text=raw_text, confidence=confidence, terms=terms)
