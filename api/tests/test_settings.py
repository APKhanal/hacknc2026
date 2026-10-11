"""Adjustable settings: code defaults, range checks, caching, and that the API actually uses them."""
import pytest

from api import settings as settings_module
from api.settings import DEFAULTS, SPEC, Settings, SettingsSource, coerce
from core.feasible import SAFE_BREACH_RATE
from core.income import NET_FACTOR
from core.rates import DEFAULT_RATES


def test_defaults_match_the_code_constants():
    assert DEFAULTS == Settings(NET_FACTOR, DEFAULT_RATES["personal"], DEFAULT_RATES["mortgage"],
                                SAFE_BREACH_RATE, 500, 104, 0.0)
    assert set(SPEC) == set(DEFAULTS.__dataclass_fields__)
    for name, (_unit, _desc, lo, hi) in SPEC.items():
        assert lo <= getattr(DEFAULTS, name) <= hi


def test_out_of_range_or_bad_values_keep_the_default():
    s = coerce({"income_net_factor": 0.7, "simulation_paths": 50_000, "personal_loan_apr": "abc",
                "horizon_weeks": 52.0, "unknown": 1})
    assert s.income_net_factor == 0.7
    assert s.simulation_paths == DEFAULTS.simulation_paths  # 50,000 is out of range
    assert s.personal_loan_apr == DEFAULTS.personal_loan_apr
    assert s.horizon_weeks == 52 and isinstance(s.horizon_weeks, int)


def test_no_database_means_code_defaults(monkeypatch):
    assert SettingsSource(database_url="")() is DEFAULTS
    monkeypatch.setenv("SETTINGS_SOURCE", "code")
    assert SettingsSource(database_url="postgresql://would-fail")() is DEFAULTS


def test_database_is_read_at_most_once_per_cache_window(monkeypatch):
    monkeypatch.setenv("SETTINGS_SOURCE", "supabase")
    source = SettingsSource(database_url="postgresql://x", cache_seconds=60)
    calls = []
    def refresh():
        calls.append(1)
        source._shared = {"safe_breach_rate": 0.2}
    monkeypatch.setattr(source, "_refresh", refresh)
    assert source().safe_breach_rate == 0.2 and source("someone").safe_breach_rate == 0.2
    assert len(calls) == 1


def test_unreachable_database_keeps_last_good_values(monkeypatch):
    monkeypatch.setenv("SETTINGS_SOURCE", "supabase")
    source = SettingsSource(database_url="postgresql://127.0.0.1:1/none", cache_seconds=0)
    assert source() == DEFAULTS  # connection refused -> defaults, no exception


def test_api_passes_settings_to_the_simulation(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from api.main import create_app
    from api.tests.test_api import offline_pipeline
    from core.run import run
    from data.cache import write_snapshot
    from data.demo import demo_snapshots

    for snapshot in demo_snapshots():
        write_snapshot(tmp_path / "cache", snapshot)
    monkeypatch.setenv("COUNTERFACTUAL_TEST_TRIGGERS", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setattr("api.pipeline.RENDER_CACHE_PATH", tmp_path / "render_cache.json")
    custom = coerce({"simulation_paths": 200, "horizon_weeks": 52})
    monkeypatch.setattr(settings_module.SettingsSource, "__call__", lambda self, customer_id=None: custom)
    seen = {}

    def simulator(model, delta, **kwargs):
        seen.update(kwargs)
        return run(model, delta, **kwargs)

    app = create_app(cache_dir=tmp_path / "cache", db_path=tmp_path / "runs.sqlite3",
                     replay_base_url="https://replay.test", pipeline=offline_pipeline(simulator=simulator))
    with TestClient(app) as client:
        r = client.post("/ask", json={"text": "Can I afford $1400 today?", "customer_id": "demo_steady"})
        assert r.status_code == 200, r.text
        result = client.get(f"/run/{r.json()['run_id']}").json()
    assert seen["n_paths"] == 200 and seen["horizon_weeks"] == 52
    assert result["n_paths"] == 200 and result["horizon_weeks"] == 52
    assert "next year" in r.json()["prose"]  # the wording follows the shorter horizon


def test_parser_uses_the_configured_tax_share(monkeypatch):
    from api.pipeline import parse
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    decision = parse("If I made $3000 off of a bonus, could I buy a $1999 iPhone 18 Pro", "rules", net_factor=0.7)
    assert decision.items[0].amount == pytest.approx(2100)
    assert decision.terms["net_factor"] == 0.7


def _source_with(monkeypatch, shared, customers):
    monkeypatch.setenv("SETTINGS_SOURCE", "supabase")
    source = SettingsSource(database_url="postgresql://x")

    def refresh():
        source._shared, source._customers = shared, customers
    monkeypatch.setattr(source, "_refresh", refresh)
    return source


def test_each_person_gets_their_own_tax_and_loan_rates(monkeypatch):
    source = _source_with(monkeypatch, {"mortgage_apr": 0.07, "horizon_weeks": 104},
                          {"jordan": {"income_net_factor": 0.75, "mortgage_apr": 0.075, "personal_loan_apr": 0.1475},
                           "alex": {"income_net_factor": 0.77, "mortgage_apr": 0.07}})
    jordan, alex, nobody = source("jordan"), source("alex"), source("unknown")
    assert (jordan.income_net_factor, jordan.mortgage_apr, jordan.personal_loan_apr) == (0.75, 0.075, 0.1475)
    assert (alex.income_net_factor, alex.personal_loan_apr) == (0.77, DEFAULTS.personal_loan_apr)
    assert nobody.mortgage_apr == 0.07  # shared value when a person has no override


def test_simulation_settings_are_never_per_person(monkeypatch):
    source = _source_with(monkeypatch, {"horizon_weeks": 104, "simulation_paths": 500},
                          {"jordan": {"horizon_weeks": 52, "simulation_paths": 2000, "safe_breach_rate": 0.4,
                                      "breach_threshold": 500}})
    jordan = source("jordan")
    assert (jordan.horizon_weeks, jordan.simulation_paths) == (104, 500)
    assert (jordan.safe_breach_rate, jordan.breach_threshold) == (DEFAULTS.safe_breach_rate, DEFAULTS.breach_threshold)


def test_per_person_values_are_random_but_stable_and_realistic():
    from data.supabase_setup import personal_value
    from api.settings import PER_CUSTOMER
    people = [f"customer-{i}" for i in range(30)]
    for key, (lo, hi, step) in PER_CUSTOMER.items():
        values = [personal_value(p, key) for p in people]
        assert all(lo <= v <= hi for v in values)
        assert all(abs(round((v - lo) / step) * step + lo - v) < 1e-9 for v in values)  # on the step grid
        assert len(set(values)) > 5  # actually varies between people
        assert values == [personal_value(p, key) for p in people]  # same person, same value every run


def test_parser_uses_the_persons_mortgage_rate(monkeypatch):
    from api.pipeline import parse
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    decision = parse("can I afford a $400k house with 20% down", "rules", settings=coerce({"mortgage_apr": 0.07375}))
    assert decision.terms["loans"][0]["rate_pct"] == 7.375
