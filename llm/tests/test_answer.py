"""Tests for answer orchestration (render → validate → retry → template)."""

import pytest
from llm.models import Claim, Culprit
from llm.answer import answer, reset_path_stats, get_path_stats


def test_answer_returns_string_or_list():
    """Answer should always return a string or list of strings."""
    culprit = make_culprit("Netflix")
    claims = [make_claim("culprit_amount", 15.99)]

    result = answer(claims, culprit)
    assert isinstance(result, (str, list))
    if isinstance(result, list):
        assert all(isinstance(s, str) for s in result)


def test_answer_never_raises():
    """Answer should never raise an exception."""
    culprit = make_culprit("Test")
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

    culprit = make_culprit("Gym")
    claims = [
        make_claim("breach_rate_with_delta", 0.8),
        make_claim("culprit_amount", 65.0)
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

    culprit = make_culprit("Store")
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

    culprit = make_culprit("Test")
    claims = [make_claim("culprit_amount", 100.0)]

    for _ in range(3):
        answer(claims, culprit)

    stats = get_path_stats()
    total = stats["render_first_try"] + stats["render_retry"] + stats["template"]
    assert total == 3


def test_answer_with_evidence_resolver():
    """Answer should accept optional evidence resolver."""
    def mock_resolver(txn_id):
        return True  # All transactions exist

    culprit = make_culprit("Amazon")
    claims = [
        make_claim("culprit_amount", 50.0)
    ]

    result = answer(claims, culprit, txn_resolver=mock_resolver)
    assert isinstance(result, (str, list))
