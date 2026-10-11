"""Spending audit: which low-priority recurring expenses cost the most, and what stopping them saves.

One noise draw, leave-one-out like attribute.rank_drivers, so every number shares the same dice.
Yearly savings come from the simulated outflow itself, so variable amounts, skipped occurrences and
late fees are included rather than assuming a flat monthly bill.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from core.model import CashflowModel
from core.simulate import make_noise, flow_components, paths_from_components

DAYS_PER_YEAR = 365
WEEKS_PER_YEAR = 52


@dataclass(frozen=True)
class AuditRow:
    obligation_id: str
    label: str
    amount: float
    cadence_days: float
    yearly_savings: float  # expected money not spent per year if stopped
    breach_rate_without: float  # odds of dipping below the threshold if this one is stopped
    variable: bool  # amounts or occurrences vary, so the saving is an expected value


@dataclass(frozen=True)
class AuditResult:
    rows: list[AuditRow]  # the top-k low-priority expenses, biggest saving first
    combined_yearly: float
    baseline_breach_rate: float
    cut_breach_rate: float
    kept: list[str]  # labels left alone (high priority)
    considered: int  # low-priority expenses compared


def audit(
    model: CashflowModel,
    priorities: dict[str, str],
    k: int = 3,
    seed: int = 1337,
    n_paths: int = 500,
    horizon_weeks: int = 104,
    breach_threshold: float = 0.0,
) -> AuditResult:
    """priorities maps obligation_id -> "high" | "low" (missing ids count as high: never suggest cutting unknowns)."""
    noise = make_noise(seed, n_paths, horizon_weeks, len(model.recurring))
    comp = flow_components(model, None, noise)
    baseline = paths_from_components(comp, breach_threshold, include_delta=False).breach_rate
    years = horizon_weeks / WEEKS_PER_YEAR
    rows = []
    for j, ob in enumerate(model.recurring):
        if priorities.get(ob.obligation_id) != "low":
            continue
        yearly = float(comp.obligations[j].sum(axis=1).mean() / years)
        without = paths_from_components(comp, breach_threshold, include_delta=False, exclude=j).breach_rate
        rows.append(AuditRow(ob.obligation_id, ob.label, ob.amount, ob.cadence_days, round(yearly, 2),
                             round(without, 4), bool(ob.amount_std or ob.skip_prob)))
    rows.sort(key=lambda r: (-r.yearly_savings, r.obligation_id))
    top = rows[:k]
    top_ids = {r.obligation_id for r in top}
    drop = [j for j, ob in enumerate(model.recurring) if ob.obligation_id in top_ids]
    cut_comp = replace(comp, obligations=np.delete(comp.obligations, drop, axis=0)) if drop else comp
    cut = paths_from_components(cut_comp, breach_threshold, include_delta=False).breach_rate
    kept = [ob.label for ob in model.recurring if priorities.get(ob.obligation_id) != "low"]
    return AuditResult(top, round(sum(r.yearly_savings for r in top), 2), round(baseline, 4), round(cut, 4),
                       kept, len(rows))
