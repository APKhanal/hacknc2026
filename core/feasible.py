"""When could the user afford this? One noise draw, the decision slid later week by week."""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from core.housing import RENT_END_LABEL
from core.loans import PROCEEDS_SUFFIX
from core.model import CashflowModel, Decision, DecisionDelta, as_decision
from core.simulate import DAYS_PER_WEEK, delta_outflow, flow_components, make_noise, paths_from_components

SAFE_BREACH_RATE = 0.10
MAX_WAIT_WEEKS = 156  # three years


@dataclass(frozen=True)
class Outlook:
    feasible: bool
    wait_weeks: int | None  # weeks later than asked
    breach_rate: float | None  # odds of dipping below zero in the 2 years after the shifted start
    monthly_gap: float | None  # when infeasible: typical monthly shortfall after the payments begin
    searched_weeks: int
    first_start_day: float = 0.0  # when the (earliest) purchase item was asked to begin, in days from today


def _is_fixed(item: DecisionDelta) -> bool:
    """Pay changes don't move when the user waits to buy; everything else (loans, purchases, rent ending) does."""
    return item.label == "Pay change" or (item.direction == "inflow" and item.label != RENT_END_LABEL
                                       and not item.label.endswith(PROCEEDS_SUFFIX))


def shifted(decision: Decision, weeks: int) -> Decision:
    days = weeks * DAYS_PER_WEEK
    items = tuple(it if _is_fixed(it) else replace(
        it, start_day=it.start_day + days, end_day=None if it.end_day is None else it.end_day + days)
        for it in decision.items)
    return replace(decision, items=items)


def find_feasible_start(
    model: CashflowModel,
    decision: Decision | DecisionDelta,
    seed: int = 1337,
    n_paths: int = 500,
    horizon_weeks: int = 104,
    max_wait_weeks: int = MAX_WAIT_WEEKS,
    safe_rate: float = SAFE_BREACH_RATE,
    breach_threshold: float = 0.0,
) -> Outlook:
    """Earliest whole-week delay after which the odds of going below the threshold are <= safe_rate.

    The odds are measured over `horizon_weeks` starting at the shifted purchase, with the same dice for
    every candidate, so the answer is monotone-ish and reproducible. Income changes are not delayed.
    """
    decision = as_decision(decision)
    movable = [it for it in decision.items if not _is_fixed(it)]
    if not movable:
        return Outlook(False, None, None, None, 0)
    start_day = float(min(it.start_day for it in movable))
    first_week = int(start_day // DAYS_PER_WEEK)
    total = first_week + max_wait_weeks + horizon_weeks
    noise = make_noise(seed, n_paths, total, len(model.recurring))
    comp = flow_components(model, None, noise)
    last = None
    for wait in range(1, max_wait_weeks + 1):
        paths = paths_from_components(replace(comp, delta=delta_outflow(shifted(decision, wait), total)),
                                      breach_threshold)
        start = first_week + wait
        window = paths.balances[:, start:start + horizon_weeks + 1]
        rate = float((window.min(axis=1) < breach_threshold).mean())
        last = paths
        if rate <= safe_rate:
            return Outlook(True, wait, round(rate, 4), None, max_wait_weeks, start_day)
    year = last.balances[:, -1] - last.balances[:, -53]
    gap = float(-np.median(year) / 12)
    return Outlook(False, None, None, round(max(gap, 0.0), 2), max_wait_weeks, start_day)
