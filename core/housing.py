"""Buying a home ends the rent: a home-purchase decision gets an offsetting "Rent ends" inflow."""
from __future__ import annotations

from dataclasses import replace

from core.model import CashflowModel, Decision, DecisionDelta

RENT_END_LABEL = "Rent ends"
_HOME_WORDS = ("house", "home", "mortgage", "condo", "townhouse", "townhome")
_RENT_WORDS = ("rent", "landlord", "lease")
MORTGAGE_MIN_YEARS = 15


def is_home_loan(loan: dict) -> bool:
    return any(w in str(loan.get("label", "")).lower() for w in _HOME_WORDS) or float(loan.get("years", 0)) >= MORTGAGE_MIN_YEARS


def resolve_housing(decision: Decision, model: CashflowModel) -> Decision:
    """If the decision buys a home and the model pays rent, stop the rent when the mortgage starts.

    The rent obligation stays in the model (it is real history); the decision carries an inflow of the
    same amount and cadence from the first rent date on/after the purchase, so net flow is unchanged
    by rent from then on. Only the largest-cadence-matching rent is ended, and only once.
    """
    loans = [ln for ln in decision.terms.get("loans", []) if is_home_loan(ln)]
    rents = [r for r in model.recurring if any(w in r.label.lower().split() for w in _RENT_WORDS)]
    if not loans or not rents or decision.terms.get("rent_end_indexes"):
        return decision
    rent = max(rents, key=lambda r: r.amount * 30 / r.cadence_days)
    start = min(float(ln.get("start_day", 0)) for ln in loans)
    first = float(rent.next_due_day)
    if first < start:
        first += -((first - start) // rent.cadence_days) * rent.cadence_days
    item = DecisionDelta(kind="recurring", amount=rent.amount, start_day=first, cadence_days=rent.cadence_days,
                         label=RENT_END_LABEL, raw_text=decision.raw_text, confidence=decision.confidence,
                         direction="inflow")
    terms = {**decision.terms, "rent_end_indexes": [len(decision.items)],
             "assumptions": [*decision.terms.get("assumptions", []), "rent_ends"],
             "rent_ended": {"label": rent.label, "amount": rent.amount, "cadence_days": rent.cadence_days}}
    return replace(decision, items=(*decision.items, item), terms=terms)
