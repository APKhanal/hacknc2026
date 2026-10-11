"""Which parser reads a question: Gemini first when a key is set, offline rules otherwise."""
from datetime import date

import pytest

from api import pipeline
from api.pipeline import RephraseRequired, describe_decision, parse

IPHONE = "If I made $3000 off of a bonus, could I buy a $1999 iPhone 18 Pro"
IPHONE_JSON = ('{"income": [{"amount": 3000, "period": "once", "replaces": false, "net": false, '
               '"start_date": null, "label": "Bonus"}], "expenses": [{"amount": 1999, "quantity": null, '
               '"cadence": "once", "months": null, "start_date": null, "label": "iPhone 18 Pro"}], '
               '"loans": [], "ignored": [18]}')


@pytest.fixture
def gemini(monkeypatch):
    calls = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def respond(payload):
        def generate_text(prompt, **kwargs):
            calls.append(prompt)
            if isinstance(payload, Exception):
                raise payload
            return payload
        monkeypatch.setattr("llm.gemini.generate_text", generate_text)
        return calls
    return respond


def test_gemini_reads_the_question_first(gemini):
    calls = gemini(IPHONE_JSON)
    decision = parse(IPHONE)
    assert len(calls) == 1 and decision.confidence == 0.8
    assert [(i.direction, i.label) for i in decision.items] == [("inflow", "Bonus"), ("outflow", "iPhone 18 Pro")]


def test_gemini_failure_falls_back_to_the_rules(gemini):
    calls = gemini(TimeoutError("network down"))
    decision = parse(IPHONE)
    assert len(calls) == 1 and decision.confidence == 0.85  # the rules built it
    assert [i.label for i in decision.items] == ["Bonus", "iPhone 18 Pro"]


def test_llm_mode_refuses_instead_of_falling_back(gemini):
    gemini(TimeoutError("network down"))
    with pytest.raises(RephraseRequired, match="Try one clear sentence"):
        parse(IPHONE, mode="llm")


def test_rules_mode_never_calls_gemini(gemini):
    calls = gemini(IPHONE_JSON)
    parse(IPHONE, mode="rules")
    assert calls == []


def test_no_amount_asks_for_one_without_calling_gemini(gemini):
    calls = gemini(IPHONE_JSON)
    with pytest.raises(RephraseRequired, match="Please include a dollar amount"):
        parse("should I buy a car")
    assert calls == []


def test_answer_describes_a_bonus_as_money_coming_in(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    text = describe_decision(parse(IPHONE), date.today())
    assert text == "Getting $2,340 today, and spending $1,999 today"
