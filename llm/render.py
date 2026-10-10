"""Render typed claims into natural prose using Gemini."""

from typing import Union, Optional
import os
import json

from core.model import Claim, Culprit


def render(
    claims: list[Claim],
    culprit: Optional[Culprit],
    violation_feedback: Optional[list[str]] = None
) -> str:
    """
    Render claims to natural prose using Gemini.

    Type signature enforces that render receives ONLY claims and culprit,
    never raw SimResult or transaction records.

    Args:
        claims: Typed claims (only source of truth for numbers)
        culprit: Culprit to name in prose
        violation_feedback: Optional violations from previous attempt (for retry)

    Returns:
        Natural prose (string or list[str] per Blocker 1 agreement)

    Raises:
        Whatever _render_with_gemini raises on a real failure (network,
        quota, auth, malformed response). This is deliberate: the caller
        (api/main.py) needs to see that a real failure happened, rather
        than silently receiving fallback text indistinguishable from a
        genuine Gemini render. _render_with_gemini itself already returns
        the fallback text directly (no exception) for the two cases that
        aren't failures - the SDK not being installed, or no API key.
    """
    return _render_with_gemini(claims, culprit, violation_feedback)


def _render_with_gemini(
    claims: list[Claim],
    culprit: Optional[Culprit],
    violation_feedback: Optional[list[str]] = None
) -> str:
    """Render using Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError:
        return _render_fallback(claims, culprit)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _render_fallback(claims, culprit)

    genai.configure(api_key=api_key)

    # Build claim summary for the prompt
    claim_summary = _build_claim_summary(claims)
    culprit_label = culprit.label if culprit is not None else "None: no positive recurring-charge contribution was measured"
    culprit_instruction = f"Name the culprit as: {culprit.label}" if culprit is not None else "Do not invent a culprit or merchant; there is no measured contributing recurring charge."

    feedback_section = ""
    if violation_feedback:
        feedback_section = f"\n\nPrevious attempt had these violations—fix them:\n"
        for violation in violation_feedback:
            feedback_section += f"- {violation}\n"

    prompt = f"""You are helping a user understand their spending analysis. Write a short, natural text message about their spending decision.

Culprit (merchant/category): {culprit_label}

Claims (the ONLY source of numbers in your response):
{claim_summary}

CRITICAL RULES:
1. Every number in your response MUST come from a claim's value field, verbatim.
2. Do not compute, round, average, or infer any figure.
3. Write numbers as digits, never spelled out.
4. NEVER hedge numerically: no "about", "around", "roughly", "~", "nearly", "almost", "over", "under" before numbers.
5. Format probabilities as whole-number percents: 0.27 → "27%" (no "about").
6. {culprit_instruction}
7. Do not reference transactions or IDs unless a claim mentions them.
8. No markdown, emoji, or bullet points. It's a text message.

Output format:
- 3–5 sentences, iMessage-appropriate
- Lead with probability if available
- Name the culprit only when one is provided
- End with a reference to reviewing the replay/details{feedback_section}

Generate the prose now:"""

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    model = genai.GenerativeModel(model_name)
    # No SDK-level retry and a short deadline: a transient failure should
    # fall through to the template immediately, not burn quota retrying.
    response = model.generate_content(
        prompt, request_options={"retry": None, "timeout": 10}
    )

    prose = response.text.strip()
    # Remove markdown if any
    prose = prose.replace("```", "").replace("**", "").replace("*", "")

    return prose


def fake_gemini_render(claims: list[Claim], culprit: Optional[Culprit]) -> str:
    """Deterministic, network-free stand-in for render() that still reads like
    a natural verdict rather than the stiff api.pipeline.checked_template
    sentence. Every number comes straight from claim.value, using the same
    formatting conventions checked_template already proved validator-safe
    (whole-percent probabilities; percentage-point deltas as bare 2-decimal
    numbers, since claim.unit == "probability" lets the validator rescale a
    0-1 claim against a 0-100 number in prose). Used by the test1-5 demo
    trigger, so a live demo never depends on Gemini being reachable, and by
    tests that want a realistic renderer without exercising the live call.
    """
    values = {c.kind: c for c in claims}
    prob_claim = values.get("breach_rate_with_delta") or values.get("baseline_breach_rate")

    sentences = []
    if prob_claim is not None:
        pct = int(round(prob_claim.value * 100))
        if pct < 20:
            verdict = "a comfortably sustainable decision"
        elif pct < 50:
            verdict = "manageable, but worth a second look"
        else:
            verdict = "a real stretch on your plan"
        sentences.append(
            f"There's a {pct}% chance this breaches your balance threshold, which makes it {verdict}."
        )
    else:
        sentences.append("The simulation did not return a breach probability to evaluate.")

    if culprit is not None:
        amount_claim = values.get("culprit_amount")
        contribution_claim = values.get("culprit_marginal_contribution")
        amount_str = _format_dollar(amount_claim.value) if amount_claim is not None else _format_dollar(culprit.amount)
        sentence = f"{culprit.label} at {amount_str} is the biggest driver"
        if contribution_claim is not None:
            points = contribution_claim.value * 100
            sentence += f", cutting the breach rate by {points:.2f} percentage points if removed"
        sentences.append(sentence + ".")
    else:
        sentences.append("No single recurring charge stood out as the driver.")

    sentences.append("Full paths and evidence are in the replay.")
    return " ".join(sentences)


def _render_fallback(claims: list[Claim], culprit: Optional[Culprit]) -> str:
    """Simple fallback rendering when Gemini unavailable."""
    if culprit is None:
        return "Review the simulation and its evidence in the replay."
    if not claims:
        return f"I analyzed your spending around {culprit.label}. Review the details in the replay."

    parts = []

    # Extract key numbers
    prob_claim = next((c for c in claims if 'prob' in c.kind.lower()), None)
    amount_claim = next((c for c in claims if 'amount' in c.kind.lower() or 'cost' in c.kind.lower()), None)

    # Lead with probability
    if prob_claim:
        prob_pct = int(round(prob_claim.value * 100))
        parts.append(f"There's a {prob_pct}% chance you can afford this.")

    # Name the culprit and add amount
    if amount_claim:
        amount_str = _format_dollar(amount_claim.value)
        parts.append(f"{culprit.label} is {amount_str}.")
    else:
        parts.append(f"I analyzed {culprit.label} in your spending.")

    # Add other relevant info
    for claim in claims:
        if claim.kind.lower() not in ['probability', 'amount', 'cost']:
            if 'risk' in claim.kind.lower():
                val = _format_value(claim.value, claim.kind)
                parts.append(f"Your risk is {val}.")

    parts.append("Check the replay for more details.")

    return " ".join(parts)


def _build_claim_summary(claims: list[Claim]) -> str:
    """Build a readable summary of claims for the prompt."""
    if not claims:
        return "(no claims)"

    lines = []
    for claim in claims:
        formatted_value = _format_value(claim.value, claim.kind)
        lines.append(f"- {claim.kind}: {formatted_value}")

    return "\n".join(lines)


def _format_dollar(value: float) -> str:
    """Format a float as a dollar amount."""
    if value == int(value):
        return f"${int(value)}"
    return f"${value:.2f}"


def _format_value(value: float, kind: str) -> str:
    """Format a value based on its kind."""
    if isinstance(value, str):
        # culprit_label's value is the merchant name itself (core.model.Claim
        # .value is `float | str` by design) - nothing to numerically format.
        return value

    kind_lower = kind.lower()

    if 'percent' in kind_lower or 'probability' in kind_lower or 'prob' in kind_lower:
        pct = int(round(value * 100))
        return f"{pct}%"
    elif 'dollar' in kind_lower or 'amount' in kind_lower or 'cost' in kind_lower:
        return _format_dollar(value)
    elif value == int(value):
        return str(int(value))
    else:
        return f"{value:.2f}"
