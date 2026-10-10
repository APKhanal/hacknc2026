"""Tests for template fallback rendering."""

import pytest
from llm.models import Claim, Culprit
from llm.template import template
from llm.validate import validate


def test_template_with_empty_claims():
    """Template should handle empty claim list safely."""
    culprit = Culprit(label="Netflix")
    prose = template([], culprit)
    assert isinstance(prose, str)
    assert len(prose) > 0
    assert "Netflix" in prose


def test_template_with_probability_claim():
    """Template should format probability claims as percents."""
    culprit = Culprit(label="Flight to NYC")
    claims = [
        Claim(kind="probability", value=0.85, evidence=[])
    ]
    prose = template(claims, culprit)
    assert "85%" in prose


def test_template_with_amount_claim():
    """Template should format dollar amounts."""
    culprit = Culprit(label="MacBook")
    claims = [
        Claim(kind="amount", value=1299.99, evidence=[])
    ]
    prose = template(claims, culprit)
    assert "$1299.99" in prose or "$1300" in prose


def test_template_output_passes_validator():
    """Template output should pass validation."""
    culprit = Culprit(label="Gym")
    claims = [
        Claim(kind="probability", value=0.75, evidence=[]),
        Claim(kind="amount", value=65.0, evidence=[])
    ]
    prose = template(claims, culprit)
    result = validate(prose, claims, culprit)
    assert result.passed, f"Violations: {result.violations}"


def test_template_with_multiple_claims():
    """Template should render multiple claim kinds."""
    culprit = Culprit(label="Car Payment")
    claims = [
        Claim(kind="probability", value=0.6, evidence=[]),
        Claim(kind="amount", value=450.0, evidence=[]),
        Claim(kind="risk", value=0.3, evidence=[])
    ]
    prose = template(claims, culprit)
    assert isinstance(prose, str)
    assert "Car Payment" in prose


def test_template_unknown_claim_kinds_skipped():
    """Template should skip unknown claim kinds gracefully."""
    culprit = Culprit(label="Test")
    claims = [
        Claim(kind="unknown_kind", value=100.0, evidence=[]),
        Claim(kind="probability", value=0.5, evidence=[])
    ]
    prose = template(claims, culprit)
    assert isinstance(prose, str)
    assert "50%" in prose
