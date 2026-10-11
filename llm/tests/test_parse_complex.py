from datetime import date
from unittest import mock

import pytest

from llm import parse_complex as pc

TODAY = date(2026, 10, 10)


def parse(text, **kw):
    return pc.parse_complex(text, TODAY, use_llm=False, **kw)


def test_house_with_job_builds_income_down_payment_and_mortgage():
    d = parse("I just got a job making $90k a year, can I afford a $350k house with 20% down at 7% over 30 years?")
    income, down, payment = d.items
    assert income.direction == "inflow" and income.cadence_days == pytest.approx(365 / 12)
    assert income.amount == pytest.approx(90_000 / 12 * 0.78, abs=0.01)  # disclosed net haircut
    assert down.kind == "one_time" and down.amount == 70_000
    assert payment.cadence_days == 30 and payment.end_day == 360 * 30
    assert payment.amount == pytest.approx(1862.85, abs=0.01)  # $280k @ 7% / 30y
    assert d.terms["replace_income"][0]["annual"] == pytest.approx(70_200)


def test_one_year_loan_ends_after_twelve_payments():
    d = parse("Can I afford a $5,000 loan at 6% for 1 year?")
    (payment,) = d.items
    assert payment.amount == pytest.approx(430.33, abs=0.01) and payment.end_day == 360


def test_raise_is_additive_inflow_and_rent_is_monthly_outflow():
    d = parse("I got a $500/month raise, can I afford $1,200/month rent?")
    raise_, rent = d.items
    assert raise_.direction == "inflow" and "replace_income" not in d.terms
    assert rent.direction == "outflow" and rent.amount == 1200 and rent.cadence_days == 30


def test_nearest_cue_wins_in_one_sentence():
    d = parse("I got a $400/month raise and want a $28k car with $4k down at 5.5% for 5 years")
    assert [i.direction for i in d.items] == ["inflow", "outflow", "outflow"]
    assert d.items[1].amount == 4000 and d.terms["loans"][0]["principal"] == 24000


def test_timing_and_fixed_length_expense():
    d = parse("can I afford $400 a month for 12 months starting in 30 days")
    (item,) = d.items
    assert item.start_day == 30 and item.end_day == 30 + 12 * 30


def test_thousands_commas_do_not_split_the_clause():
    d = parse("Can I afford a $5,000 loan at 6% for 1 year?")
    assert d.terms["loans"][0]["price"] == 5000


@pytest.mark.parametrize("text", [
    "can I afford a $350k house at 7%",                 # rate without a term: not guessed
    "can I afford $400 and also $90 at 3% somewhere",  # stray percentage
    "I make $50 an hour, can I afford $400?",           # hourly pay unsupported
])
def test_unaccounted_numbers_are_refused_not_dropped(text):
    with pytest.raises(pc.ComplexParseError):
        parse(text)


def test_plain_single_expense_still_takes_the_legacy_path():
    assert not pc.needs_complex("Can I afford $400 today?")
    assert not pc.needs_complex("Can I afford $1,400 on December 5th?")
    assert pc.needs_complex("Can I afford $65/month starting in 30 days?")
    assert pc.needs_complex("I got a raise, can I afford $400?")


def _stub_llm(payload):
    return mock.patch.dict("os.environ", {"GEMINI_API_KEY": "x"}), mock.patch(
        "llm.gemini.generate_text", return_value=payload)


def test_llm_fallback_accepts_faithful_extraction():
    text = "my sister is lending me twelve grand then I owe $300 each month for 5 years at 4%"
    payload = ('{"income": [], "expenses": [], "loans": [{"price": 300, "down": null, "down_pct": null, '
               '"rate_pct": 4, "years": 5, "start_day": 0, "label": "loan"}]}')
    env, gen = _stub_llm(payload)
    with env, gen:
        d = pc.parse_complex(text, TODAY)
    assert d.confidence == 0.7  # capped when the LLM helped
    assert d.terms["loans"][0]["monthly_payment"] == pytest.approx(5.52, abs=0.01)  # code did the math


def test_llm_fallback_rejects_invented_or_dropped_numbers():
    text = "my sister is lending me a bit then I owe $300 at 4% for 5 years"
    invented = ('{"income": [], "expenses": [], "loans": [{"price": 12000, "down": null, "down_pct": null, '
                '"rate_pct": 4, "years": 5, "start_day": 0, "label": "loan"}]}')
    env, gen = _stub_llm(invented)
    with env, gen, pytest.raises(pc.ComplexParseError):
        pc.parse_complex(text, TODAY)


def test_llm_unavailable_gives_a_rephrase_hint(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(pc.ComplexParseError) as exc:
        pc.parse_complex("buy something for $400 at 3%", TODAY)
    assert "Try one clear sentence" in str(exc.value)


def test_two_loans_one_with_stated_payment_and_bare_numbers():
    d = parse("I make 3000 a month from my new job but want to get a 300000 house with 30 year mortgage "
              "7 percent yearly interest with 6000 dollar down and I take a 3000 dollar loan with "
              "300 dollar monthly payment over 1 year")
    income, down, mortgage, loan = d.items
    assert income.direction == "inflow" and income.amount == pytest.approx(3000 * 0.78)
    assert down.amount == 6000 and down.kind == "one_time"
    assert mortgage.amount == pytest.approx(1955.99, abs=0.01) and mortgage.end_day == 360 * 30
    assert loan.amount == 300 and loan.end_day == 12 * 30  # stated payment used as-is, no rate invented
    assert d.terms["loans"][1]["rate_pct"] is None
    assert d.terms["replace_income"][0]["annual"] == pytest.approx(3000 * 12 * 0.78)


def test_stated_payment_that_cannot_repay_the_loan_is_refused():
    with pytest.raises(pc.ComplexParseError):
        parse("can I take a $3000 loan with a $100 monthly payment over 1 year")
