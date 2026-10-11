"""Seeded, vectorized Monte Carlo cashflow engine.

Weekly ticks. Week w covers days [7w, 7w + 7). balances[:, 0] is the opening
balance and balances[:, w] is the balance at the end of week w, so a PathSet
has horizon_weeks + 1 columns.

All randomness lives in a NoiseTensor drawn once from the seed. The engine
itself is a pure function of (model, delta, noise, excluded obligations), which
is what lets attribute() change one variable while keeping the same dice.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.model import CashflowModel, Decision, DecisionDelta, as_decision

DAYS_PER_WEEK = 7
LATE_FEE = 35.00

# Policy vector ranges, sampled once per path.
DISCIPLINE_RANGE = (0.7, 1.3)
SHOCK_PROB_RANGE = (0.005, 0.03)
SHOCK_MAGNITUDE_RANGE = (200.0, 1500.0)
LATE_PROB_RANGE = (0.0, 0.08)


@dataclass(frozen=True)
class NoiseTensor:
    """Every random draw a run will ever use. Generate once, index many times."""

    discipline: np.ndarray  # (n_paths,)
    shock_prob: np.ndarray  # (n_paths,)
    shock_magnitude: np.ndarray  # (n_paths,)
    late_prob: np.ndarray  # (n_paths,)
    income_z: np.ndarray  # (n_paths, horizon_weeks) standard normal
    discretionary_z: np.ndarray  # (n_paths, horizon_weeks) standard normal
    shock_u: np.ndarray  # (n_paths, horizon_weeks) uniform [0, 1)
    late_u: np.ndarray  # (n_paths, horizon_weeks, n_obligations) uniform [0, 1)
    amount_z: np.ndarray  # (n_paths, horizon_weeks, n_obligations) standard normal, variable charge sizes
    skip_u: np.ndarray  # (n_paths, horizon_weeks, n_obligations) uniform [0, 1), occurrences that don't happen

    @property
    def n_paths(self) -> int:
        return self.discipline.shape[0]

    @property
    def horizon_weeks(self) -> int:
        return self.income_z.shape[1]


def make_noise(seed: int, n_paths: int, horizon_weeks: int, n_obligations: int) -> NoiseTensor:
    # Draw order is part of the determinism contract. Append new draws at the end only.
    rng = np.random.default_rng(seed)
    return NoiseTensor(
        discipline=rng.uniform(*DISCIPLINE_RANGE, size=n_paths),
        shock_prob=rng.uniform(*SHOCK_PROB_RANGE, size=n_paths),
        shock_magnitude=rng.uniform(*SHOCK_MAGNITUDE_RANGE, size=n_paths),
        late_prob=rng.uniform(*LATE_PROB_RANGE, size=n_paths),
        income_z=rng.standard_normal((n_paths, horizon_weeks)),
        discretionary_z=rng.standard_normal((n_paths, horizon_weeks)),
        shock_u=rng.random((n_paths, horizon_weeks)),
        late_u=rng.random((n_paths, horizon_weeks, n_obligations)),
        amount_z=rng.standard_normal((n_paths, horizon_weeks, n_obligations)),
        skip_u=rng.random((n_paths, horizon_weeks, n_obligations)),
    )


@dataclass(frozen=True)
class PathSet:
    balances: np.ndarray  # (n_paths, horizon_weeks + 1)
    breach_threshold: float

    @property
    def n_paths(self) -> int:
        return self.balances.shape[0]

    @property
    def horizon_weeks(self) -> int:
        return self.balances.shape[1] - 1

    @property
    def min_balance(self) -> np.ndarray:
        return self.balances.min(axis=1)

    @property
    def breached(self) -> np.ndarray:
        return self.min_balance < self.breach_threshold

    @property
    def first_breach_week(self) -> np.ndarray:
        """Week index of first breach per path, -1 where the path never breaches."""
        below = self.balances < self.breach_threshold
        return np.where(below.any(axis=1), below.argmax(axis=1), -1)

    @property
    def breach_rate(self) -> float:
        return float(self.breached.mean())


def occurrences_per_week(
    next_due_day: float, cadence_days: float, horizon_weeks: int, end_day: float | None = None
) -> np.ndarray:
    """How many times a cadence fires in each week of the horizon.

    Handles non-integer cadence (real paychecks land every 14.3 days) and a
    next_due_day in the past (rolled forward to the first future occurrence).
    """
    horizon_days = horizon_weeks * DAYS_PER_WEEK
    if end_day is not None:
        horizon_days = min(horizon_days, float(end_day))
    first = float(next_due_day)
    if first < 0:
        first += np.ceil(-first / cadence_days) * cadence_days
    if first >= horizon_days:
        return np.zeros(horizon_weeks, dtype=np.int64)
    days = np.arange(first, horizon_days, cadence_days)
    weeks = np.floor(days / DAYS_PER_WEEK).astype(np.int64)
    weeks = weeks[weeks < horizon_weeks]
    return np.bincount(weeks, minlength=horizon_weeks)


def _item_outflow(item: DecisionDelta, horizon_weeks: int) -> np.ndarray:
    out = np.zeros(horizon_weeks)
    start = max(float(item.start_day), 0.0)
    sign = item.signed_amount
    if item.kind == "one_time":
        week = int(start // DAYS_PER_WEEK)
        if week < horizon_weeks:
            out[week] = sign
        return out
    return occurrences_per_week(start, item.cadence_days, horizon_weeks, item.end_day) * sign


def delta_outflow(delta: DecisionDelta | Decision | None, horizon_weeks: int) -> np.ndarray:
    """Deterministic weekly net outflow from the proposed decision. Positive = money out, negative = money in."""
    out = np.zeros(horizon_weeks)
    decision = as_decision(delta)
    if decision is None:
        return out
    for item in decision.items:
        out += _item_outflow(item, horizon_weeks)
    return out


def _obligation_outflows(model: CashflowModel, noise: NoiseTensor) -> np.ndarray:
    """(n_obligations, n_paths, horizon_weeks) outflow per obligation, including late slips.

    A late bill slips one week and picks up LATE_FEE. Each obligation reads its
    own slice of late_u, so removing one never perturbs another's draws.
    """
    n, h = noise.n_paths, noise.horizon_weeks
    out = np.zeros((len(model.recurring), n, h))
    late_prob = noise.late_prob[:, None]
    for j, ob in enumerate(model.recurring):
        count = occurrences_per_week(ob.next_due_day, ob.cadence_days, h)  # (h,)
        if ob.skip_prob > 0 or ob.amount_std > 0:
            # Variable spend: each scheduled charge may not happen, and the ones that do vary in size.
            happen = np.where(noise.skip_u[:, :, j] < ob.skip_prob, 0.0, 1.0) * count  # (n, h)
            size = np.maximum(ob.amount + ob.amount_std * noise.amount_z[:, :, j], 0.0)
            due = happen * size
        else:
            due = np.broadcast_to(count * ob.amount, (n, h))
        late = (noise.late_u[:, :, j] < late_prob) & (due > 0)  # (n, h)
        on_time = np.where(late, 0.0, due)
        slipped = np.where(late, due + LATE_FEE, 0.0)
        out[j] = on_time
        out[j, :, 1:] += slipped[:, :-1]  # slips past the horizon fall off the end
    return out


def _base_netflow(model: CashflowModel, noise: NoiseTensor) -> np.ndarray:
    """(n_paths, horizon_weeks) income minus discretionary minus shocks. No obligations, no delta."""
    h = noise.horizon_weeks
    inc = model.income
    paydays = occurrences_per_week(inc.next_due_day, inc.cadence_days, h)  # (h,)
    income = paydays * inc.mean + np.sqrt(paydays) * inc.std * noise.income_z
    income = np.maximum(income, 0.0)

    disc = model.discretionary
    spend = disc.weekly_mean * noise.discipline[:, None] + disc.weekly_std * noise.discretionary_z
    spend = np.maximum(spend, 0.0)

    shocks = np.where(noise.shock_u < noise.shock_prob[:, None], noise.shock_magnitude[:, None], 0.0)
    return income - spend - shocks


@dataclass(frozen=True)
class FlowComponents:
    """Precomputed pieces so leave-one-out runs are a subtraction, not a re-simulation."""

    opening_balance: float
    base: np.ndarray  # (n_paths, horizon_weeks)
    obligations: np.ndarray  # (n_obligations, n_paths, horizon_weeks)
    delta: np.ndarray  # (horizon_weeks,)


def flow_components(model: CashflowModel, delta: DecisionDelta | Decision | None, noise: NoiseTensor) -> FlowComponents:
    if noise.late_u.shape[2] != len(model.recurring):
        raise ValueError(
            f"noise tensor built for {noise.late_u.shape[2]} obligations, model has {len(model.recurring)}"
        )
    return FlowComponents(
        opening_balance=model.opening_balance,
        base=_base_netflow(model, noise),
        obligations=_obligation_outflows(model, noise),
        delta=delta_outflow(delta, noise.horizon_weeks),
    )


def paths_from_components(
    comp: FlowComponents,
    breach_threshold: float,
    include_delta: bool = True,
    exclude: int | None = None,
) -> PathSet:
    """Assemble balances from components, optionally dropping the delta or one obligation."""
    obligations = comp.obligations if exclude is None else np.delete(comp.obligations, exclude, axis=0)
    net = comp.base - obligations.sum(axis=0)
    if include_delta:
        net = net - comp.delta
    n = net.shape[0]
    balances = np.empty((n, net.shape[1] + 1))
    balances[:, 0] = comp.opening_balance
    np.cumsum(net, axis=1, out=balances[:, 1:])
    balances[:, 1:] += comp.opening_balance
    return PathSet(balances=balances, breach_threshold=breach_threshold)


def simulate(
    model: CashflowModel,
    delta: DecisionDelta | Decision | None,
    seed: int = 1337,
    n_paths: int = 500,
    horizon_weeks: int = 104,
    breach_threshold: float = 0.0,
) -> PathSet:
    noise = make_noise(seed, n_paths, horizon_weeks, len(model.recurring))
    return paths_from_components(flow_components(model, delta, noise), breach_threshold)
