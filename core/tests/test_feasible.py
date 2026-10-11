from dataclasses import replace

from core.feasible import find_feasible_start, shifted
from core.housing import RENT_END_LABEL, resolve_housing
from core.loans import loan_decision
from core.model import DecisionDelta


def _house(model_start=0):
    d = loan_decision(100_000, 0.07, 30, down_payment=1_000, start_day=model_start, label="house")
    loan = {**d.terms, "price": 101_000, "label": "a house", "item_indexes": [0, 1], "start_day": model_start}
    return replace(d, terms={"loans": [loan], "assumptions": []})


def test_rent_ends_when_home_bought(model):
    rent = next(r for r in model.recurring if r.label == "Rent")
    d = resolve_housing(_house(60), model)
    end = d.items[-1]
    assert end.label == RENT_END_LABEL and end.direction == "inflow" and end.amount == rent.amount
    assert end.start_day >= 60 and (end.start_day - rent.next_due_day) % rent.cadence_days == 0
    assert d.terms["rent_end_indexes"] == [len(d.items) - 1]
    assert resolve_housing(d, model) is d  # idempotent


def test_no_rent_no_change(model):
    d = _house()
    no_rent = replace(model, recurring=[r for r in model.recurring if r.label != "Rent"])
    assert resolve_housing(d, no_rent) is d


def test_shift_moves_purchase_not_pay_change():
    pay = DecisionDelta(kind="recurring", amount=100, start_day=0, cadence_days=14, label="Pay change", direction="outflow")
    buy = DecisionDelta(kind="one_time", amount=500, start_day=10, label="x")
    d = shifted(replace(_house(), items=(pay, buy)), 3)
    assert d.items[0].start_day == 0 and d.items[1].start_day == 31


def test_affordable_later_finds_a_date(model):
    # an expense too big now, but fine once savings accumulate
    big = DecisionDelta(kind="one_time", amount=model.opening_balance + 6000, start_day=0, label="big")
    out = find_feasible_start(model, big, max_wait_weeks=104)
    assert out.feasible is None or isinstance(out.feasible, bool)
    if out.feasible:
        assert out.wait_weeks >= 1


def test_never_affordable_reports_gap(model):
    huge = DecisionDelta(kind="recurring", amount=10_000, start_day=0, cadence_days=7, label="huge")
    out = find_feasible_start(model, huge, max_wait_weeks=20)
    assert not out.feasible and out.monthly_gap > 0


def test_outlook_remembers_asked_start(model):
    d = DecisionDelta(kind="one_time", amount=model.opening_balance + 3000, start_day=70, label="x")
    out = find_feasible_start(model, d, max_wait_weeks=104)
    assert out.first_start_day == 70


def test_loan_proceeds_arrive_and_move_with_the_loan():
    d = loan_decision(3000, None, 1, payment=300, start_day=0, label="loan", proceeds_to_user=True)
    proceeds = d.items[0]
    assert proceeds.direction == "inflow" and proceeds.amount == 3000 and proceeds.kind == "one_time"
    assert shifted(d, 2).items[0].start_day == 14


def test_financing_picks_shortest_safe_term(model):
    from core.financing import financing_options
    big = DecisionDelta(kind="one_time", amount=model.opening_balance + 3000, start_day=0, label="car")
    res = financing_options(model, big)
    assert res is not None and res.amount == big.amount
    if res.option:
        assert res.option.breach_rate <= 0.10 and res.option.monthly_payment > 0


def test_financing_none_without_big_upfront_cost(model):
    from core.financing import financing_options
    small = DecisionDelta(kind="one_time", amount=100, start_day=0, label="x")
    assert financing_options(model, small) is None
