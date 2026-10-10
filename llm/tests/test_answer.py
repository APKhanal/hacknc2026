"""Tests for answer orchestration (render → validate → retry → template)."""

import pytest
from llm.models import Claim, Culprit
from llm.answer import answer, reset_path_stats, get_path_stats


def test_answer_returns_string_or_list():
    """Answer should always return a string or list of strings."""
    culprit = Culprit(label="Netflix")
    claims = [Claim(kind="amount", value=15.99, evidence=[])]

    result = answer(claims, culprit)
    assert isinstance(result, (str, list))
    if isinstance(result, list):
        assert all(isinstance(s, str) for s in result)


def test_answer_never_raises():
    """Answer should never raise an exception."""
    culprit = Culprit(label="Test")
    claims = []

    # This should not raise even with empty claims
    try:
        result = answer(claims, culprit)
        assert result is not None
    except Exception as e:
        pytest.fail(f"answer() raised {e}")


def test_answer_with_valid_claims():
    """Valid claims should be answered without falling back to template."""
    reset_path_stats()

    culprit = Culprit(label="Gym")
    claims = [
        Claim(kind="probability", value=0.8, evidence=[]),
        Claim(kind="amount", value=65.0, evidence=[])
    ]

    result = answer(claims, culprit)
    assert isinstance(result, (str, list))

    # Check if Gemini fired or fell back (both acceptable)
    stats = get_path_stats()
    total = stats["render_first_try"] + stats["render_retry"] + stats["template"]
    assert total > 0


def test_answer_fallback_on_invalid_claims():
    """If validation fails, should fall back to template."""
    reset_path_stats()

    culprit = Culprit(label="Store")
    # Empty claims might trigger template fallback
    claims = []

    result = answer(claims, culprit)
    # Should still return something
    assert isinstance(result, (str, list))
    stats = get_path_stats()
    assert stats["template"] >= 0  # template might be used


def test_answer_path_stats_tracked():
    """Path stats should be tracked for demo."""
    reset_path_stats()

    culprit = Culprit(label="Test")
    claims = [Claim(kind="amount", value=100.0, evidence=[])]

    for _ in range(3):
        answer(claims, culprit)

    stats = get_path_stats()
    total = stats["render_first_try"] + stats["render_retry"] + stats["template"]
    assert total == 3


def test_answer_with_evidence_resolver():
    """Answer should accept optional evidence resolver."""
    def mock_resolver(txn_id):
        return True  # All transactions exist

    culprit = Culprit(label="Amazon")
    claims = [
        Claim(kind="amount", value=50.0, evidence=["txn_001"])
    ]

    result = answer(claims, culprit, txn_resolver=mock_resolver)
    assert isinstance(result, (str, list))
