"""Tests for template fallback rendering."""

import pytest
from llm.models import Claim, Culprit
from llm.template import template
from llm.validate import validate


def test_template_with_empty_claims():
    """Template should handle empty claim list safely."""
    culprit = make_culprit("Netflix")
    prose = template([], culprit)
    assert isinstance(prose, str)
    assert len(prose) > 0
    assert "Netflix" in prose


def test_template_with_probability_claim():
    """Template should format probability claims as percents."""
    culprit = make_culprit("Flight to NYC")
    claims = [
        make_claim("breach_rate_with_delta", 0.85)
    ]
    prose = template(claims, culprit)
    assert "85%" in prose


def test_template_with_amount_claim():
    """Template should format dollar amounts."""
    culprit = make_culprit("MacBook")
    claims = [
        make_claim("culprit_amount", 1299.99)
    ]
    prose = template(claims, culprit)
    assert "$1299.99" in prose or "$1300" in prose


def test_template_output_passes_validator():
    """Template output should pass validation."""
    culprit = make_culprit("Gym")
    claims = [
        make_claim("breach_rate_with_delta", 0.75),
        make_claim("culprit_amount", 65.0)
    ]
    prose = template(claims, culprit)
    result = validate(prose, claims, culprit)
    assert result.passed, f"Violations: {result.violations}"


def test_template_with_multiple_claims():
    """Template should render multiple claim kinds."""
    culprit = make_culprit("Car Payment")
    claims = [
        make_claim("breach_rate_with_delta", 0.6),
        make_claim("culprit_amount", 450.0),
        make_claim("median_min_balance", 0.3)
    ]
    prose = template(claims, culprit)
    assert isinstance(prose, str)
    assert "Car Payment" in prose


def test_template_unknown_claim_kinds_skipped():
    """Template should skip unknown claim kinds gracefully."""
    culprit = make_culprit("Test")
    claims = [
        make_claim("unknown_kind", 100.0),
        make_claim("breach_rate_with_delta", 0.5)
    ]
    prose = template(claims, culprit)
    assert isinstance(prose, str)
    assert "50%" in prose
