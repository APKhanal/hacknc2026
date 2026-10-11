from dataclasses import replace

import numpy as np

from core.audit import audit
from core.model import RecurringObligation
from core.simulate import make_noise, flow_components, paths_from_components
from llm.priority import keyword_priority


def _ob(oid, label, amount, cadence=30.0, **kw):
    return RecurringObligation(oid, label, None, amount, cadence, 3.0, **kw)


def test_top_three_low_priority_ranked_by_yearly_savings(model):
    obs = [_ob("a", "Netflix", 15), _ob("b", "DoorDash", 60, 7.0), _ob("c", "Gym", 40), _ob("d", "Hulu", 12),
           _ob("e", "Rent", 1500)]
    m = replace(model, recurring=obs)
    pri = {"a": "low", "b": "low", "c": "low", "d": "low", "e": "high"}
    res = audit(m, pri)
    assert [r.label for r in res.rows] == ["DoorDash", "Gym", "Netflix"]
    assert res.kept == ["Rent"] and res.considered == 4
    assert abs(res.rows[0].yearly_savings - 60 * 365 / 7) < 120  # ~52 weekly charges, plus late-fee slack
    assert res.cut_breach_rate <= res.baseline_breach_rate


def test_unknown_priority_is_never_cut(model):
    res = audit(replace(model, recurring=[_ob("a", "Mystery", 99)]), {})
    assert res.rows == [] and res.kept == ["Mystery"]


def test_variable_spend_changes_outflow_but_fixed_bills_do_not(model):
    fixed = replace(model, recurring=[_ob("a", "DoorDash", 60, 7.0)])
    varying = replace(model, recurring=[_ob("a", "DoorDash", 60, 7.0, amount_std=20, skip_prob=0.5)])
    out = lambda m: flow_components(m, None, make_noise(1, 300, 104, 1)).obligations[0]
    f, v = out(fixed), out(varying)
    assert np.allclose(f.std(axis=0)[:20], 0, atol=40)  # only late slips vary
    assert v.std() > f.std()
    assert abs(v.sum(axis=1).mean() / f.sum(axis=1).mean() - 0.5) < 0.1  # half the charges skipped


def test_non_monthly_cadences_count_occurrences(model):
    for cadence in (7.0, 14.0, 45.0, 90.0):
        m = replace(model, recurring=[_ob("a", "X", 10, cadence)])
        res = audit(m, {"a": "low"}, n_paths=50)
        base = 10 * 365 / cadence  # plus the late fees stopping would also avoid
        assert base - 25 < res.rows[0].yearly_savings < base + 100


def test_keyword_priority():
    assert keyword_priority("Geico") == "high" and keyword_priority("State Farm Insurance") == "high"
    assert keyword_priority("Rent") == "high" and keyword_priority("Ally Auto") == "high"
    assert keyword_priority("DoorDash") == "low" and keyword_priority("Planet Fitness") == "low"
    assert keyword_priority("Spotify") == "low" and keyword_priority("Current Coffee Club") == "low"
