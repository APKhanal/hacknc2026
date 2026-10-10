"""Deterministic template fallback for rendering claims to prose."""

from typing import Union
from llm.models import Claim, Culprit


def template(claims: list[Claim], culprit: Culprit) -> Union[str, list[str]]:
    """
    Deterministic string formatting from claims. No model calls. No network.

    Returns a single string or list[str] per agreed format with Dev D.
    For now, returning a single string. Update after Blocker 1.
    """
    if not claims:
        return f"I analyzed your spending around {culprit.label}. Could you give me more details about what you're considering?"

    sentences = []

    # Extract probability claim if available
    prob_claim = next((c for c in claims if 'prob' in c.kind.lower()), None)
    if prob_claim:
        prob_pct = int(round(prob_claim.value * 100))
        sentences.append(f"There's a {prob_pct}% chance you can afford this {culprit.label}.")

    # Extract amount claim if available
    amount_claim = next((c for c in claims if 'amount' in c.kind.lower() or 'cost' in c.kind.lower()), None)
    if amount_claim:
        amount_fmt = _format_dollar(amount_claim.value)
        sentences.append(f"{culprit.label} costs {amount_fmt}.")

    # Add other claims (skipping unknown kinds gracefully)
    for claim in claims:
        if claim.kind.lower() not in ['probability', 'amount', 'cost']:
            if 'recurring' in claim.kind.lower():
                sentences.append(f"This will recur {claim.value} times.")
            elif 'risk' in claim.kind.lower():
                sentences.append(f"Your risk exposure is {_format_value(claim.value, claim.kind)}.")

    if not sentences:
        return f"I analyzed your spending around {culprit.label}. Review the details in the replay."

    prose = " ".join(sentences)
    if len(prose) > 280:
        prose = prose[:277] + "..."

    # Ensure culprit is in the prose
    if culprit.label.lower() not in prose.lower():
        prose = f"{culprit.label}: " + prose

    return prose


def _format_dollar(value: float) -> str:
    """Format a float as a dollar amount."""
    if value == int(value):
        return f"${int(value)}"
    return f"${value:.2f}"


def _format_value(value: float, kind: str) -> str:
    """Format a value based on its kind."""
    kind_lower = kind.lower()

    if 'percent' in kind_lower or 'probability' in kind_lower or 'prob' in kind_lower:
        pct = int(round(value * 100))
        return f"{pct}%"
    elif 'dollar' in kind_lower or 'amount' in kind_lower or 'cost' in kind_lower:
        return _format_dollar(value)
    return str(value)
