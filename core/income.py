"""Income-change helpers: tax haircut for gross salary talk, and resolving "new job" against the fitted paycheck."""
from __future__ import annotations

from dataclasses import replace

from core.model import CashflowModel, Decision, DecisionDelta

# Salary talk ("making $90k") is gross but the model's paychecks are net deposits.
# One flat, disclosed assumption beats comparing gross to net.
NET_FACTOR = 0.78


def current_annual_income(model: CashflowModel) -> float:
    return model.income.mean * 365 / model.income.cadence_days


def resolve_income_changes(decision: Decision, model: CashflowModel) -> Decision:
    """Turn "new job paying X" placeholders into the *difference* from the fitted paycheck.

    The parser can't see the user's current pay, so a replacing income is carried as
    terms["replace_income"] = [{"index", "annual"}] and resolved here, where the model is known.
    """
    pending = decision.terms.get("replace_income")
    if not pending:
        return decision
    items = list(decision.items)
    changes = []
    current = current_annual_income(model)
    cadence = model.income.cadence_days
    for r in pending:
        i = r["index"]
        item = items[i]
        diff_per_pay = (float(r["annual"]) - current) * cadence / 365
        changes.append({"current_annual": round(current, 2), "new_annual": float(r["annual"])})
        if abs(diff_per_pay) < 0.01:  # same pay: keep a zero item so loan item indexes stay valid
            items[i] = replace(item, amount=0.0, cadence_days=cadence, label="Pay change")
            continue
        items[i] = replace(item, amount=round(abs(diff_per_pay), 2), cadence_days=cadence,
                           direction="inflow" if diff_per_pay > 0 else "outflow",
                           label="Pay change")
    kept = tuple(items)
    if all(it.amount == 0 for it in kept):
        raise ValueError("That pay is about what you already earn, so nothing changes.")
    terms = {k: v for k, v in decision.terms.items() if k != "replace_income"}
    terms["income_changes"] = changes
    return replace(decision, items=kept, terms=terms)
