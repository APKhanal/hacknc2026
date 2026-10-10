"""Test fixtures for LLM tests."""

import pytest
from core.model import Culprit, Claim


@pytest.fixture
def make_culprit():
    """Factory for creating test Culprit objects."""
    def _make_culprit(label: str, **kwargs):
        """Create a Culprit with the given label and optional overrides."""
        defaults = {
            'obligation_id': 'test_ob',
            'label': label,
            'amount': 100.0,
            'breach_rate_without': 0.1,
            'marginal_contribution': 0.2,
            'evidence': [],
            'essential': False,
        }
        defaults.update(kwargs)
        return Culprit(**defaults)

    return _make_culprit


@pytest.fixture
def make_claim():
    """Factory for creating test Claim objects."""
    _counter = {'value': 0}

    def _make_claim(kind: str, value, unit: str = "usd", evidence=None, **kwargs):
        """Create a Claim with the given parameters."""
        if evidence is None:
            evidence = []
        _counter['value'] += 1
        defaults = {
            'claim_id': f'c{_counter["value"]}',
            'kind': kind,
            'value': value,
            'unit': unit,
            'evidence': evidence,
        }
        defaults.update(kwargs)
        return Claim(**defaults)

    return _make_claim
