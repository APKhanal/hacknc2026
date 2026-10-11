import pytest

from api.audit import parse_audit


@pytest.mark.parametrize("text", [
    "Where can I save money?", "what can I cut back on", "Which subscriptions should I cancel to save more?",
    "what if I stopped paying for my subscriptions", "Reduce my spending please", "spending audit"])
def test_audit_phrasings(text):
    assert parse_audit(text)


@pytest.mark.parametrize("text", [
    "Can I afford $1400 today?", "I want to save for a house, can I afford $2000 a month?",
    "How much would I lose per year on a $7 coffee 3 times a week?", "hello"])
def test_not_audits(text):
    assert not parse_audit(text)
