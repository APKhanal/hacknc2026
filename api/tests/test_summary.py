"""Plain-English message: wording shared with web/lib/summary.ts, plus the
parse/validate/render behavior behind it."""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.pipeline import RephraseRequired, _odds, readable_response, validate_delta
from core.model import Claim, Culprit, DecisionDelta

CASES = json.loads((Path(__file__).resolve().parents[2] / "web" / "tests" / "summary-cases.json").read_text())
TODAY = date.fromisoformat(CASES["today"])


def make_result(spec, culprit=None):
    paths = [SimpleNamespace(balances=b, min_balance=min(b), first_breach_week=fb) for b, fb in spec["paths"]]
    return SimpleNamespace(
        n_paths=len(paths), horizon_weeks=len(paths[0].balances) - 1, breach_threshold=0.0,
        baseline_breach_rate=spec["baseline_breach_rate"], delta_breach_rate=spec["delta_breach_rate"],
        median_min_balance=spec["median_min_balance"], culprit=culprit, paths=paths)


def make_delta(spec):
    return DecisionDelta(spec["kind"], spec["amount"], spec["start_day"], spec["cadence_days"])


@pytest.mark.parametrize("rate,expected", CASES["odds"])
def test_odds_match_web(rate, expected):
    assert _odds(rate) == expected


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["name"])
def test_verdict_and_dip_match_web(case):
    prose = readable_response(make_result(case["result"]), make_delta(case["delta"]), "", TODAY)
    paragraphs = prose.split("\n\n")
    assert paragraphs[0] == case["verdict"]
    if case["dip"] is None:
        assert paragraphs[1].startswith("Chance your balance dips below $0")
    else:
        assert paragraphs[1] == case["dip"]


def test_message_layout_and_odds_block():
    case = CASES["cases"][0]
    prose = readable_response(make_result(case["result"]), make_delta(case["delta"]), "", TODAY)
    assert "Chance your balance dips below $0 in the next 4 weeks:\nWith it: 100%\nWithout it: 4%" in prose
    assert prose.endswith("This is a forecast from 5 simulations, not a guarantee.")
    for jargon in ("breach", "delta", "culprit", "percentile", "threshold"):
        assert jargon not in prose.lower()


@pytest.mark.parametrize("contribution,shown", [(0.028, False), (0.05, True), (0.2, True)])
def test_driver_sentence_only_when_it_moves_the_odds(contribution, shown):
    case = CASES["cases"][0]
    culprit = Culprit("rec_1", "DoorDash", 57.97, 0.9, contribution)
    prose = readable_response(make_result(case["result"], culprit), make_delta(case["delta"]),
                              "DoorDash at $57.97 per payment is what squeezes you most.", TODAY)
    assert ("DoorDash" in prose) is shown


def test_parser_defaults_a_missing_date_to_today():
    from llm.parse import _parse_heuristic
    delta = _parse_heuristic("Should I sign up for a $60 a month gym membership?", TODAY)
    assert (delta.kind, delta.amount, delta.cadence_days, delta.start_day) == ("recurring", 60, 30, 0)
    assert validate_delta(delta) is delta


def test_missing_amount_asks_for_one():
    from llm.parse import _parse_heuristic
    with pytest.raises(RephraseRequired, match="Please include a dollar amount"):
        validate_delta(_parse_heuristic("should I buy a car", TODAY))


def test_renderer_skips_gemini_without_a_contributor(monkeypatch):
    import llm.render as render
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    def no_call(*args, **kwargs):
        raise AssertionError("Gemini should not be called")
    monkeypatch.setattr(render, "generate_text", no_call)
    assert render.render([], None) == "No single recurring bill stands out as the cause."


def test_renderer_only_shows_gemini_the_contributor(monkeypatch):
    import llm.render as render
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    prompts = []
    def capture(prompt, **kwargs):
        prompts.append(prompt)
        return "DoorDash at $57.97 per payment is what squeezes you most."
    monkeypatch.setattr(render, "generate_text", capture)
    claims = [Claim("a", "baseline_breach_rate", 0.036, "probability", ["t"]),
              Claim("b", "breach_rate_with_delta", 0.992, "probability", ["t"]),
              Claim("c", "median_min_balance", -798.5, "usd", ["t"]),
              Claim("d", "culprit_label", "DoorDash", None, ["t"]),
              Claim("e", "culprit_amount", 57.97, "usd", ["t"])]
    culprit = Culprit("rec_1", "DoorDash", 57.97, 0.9, 0.2)
    assert render.render(claims, culprit).startswith("DoorDash")
    claim_lines = prompts[0].split("Claims (the ONLY source of numbers in your response):")[1].split("CRITICAL RULES")[0]
    assert "culprit_label: DoorDash" in claim_lines and "culprit_amount: $57.97" in claim_lines
    assert "breach_rate" not in claim_lines and "median_min_balance" not in claim_lines


def test_multi_item_decision_wording_matches_the_web():
    from api.pipeline import decision_notes, describe_decision
    from core.model import Decision
    for case in CASES["decision_cases"]:
        decision = Decision.from_dict(case["decision"])
        assert describe_decision(decision, TODAY) == case["phrase"], case["name"]
        assert (decision_notes(decision) or None) == case["note"], case["name"]
