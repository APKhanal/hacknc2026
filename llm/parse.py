"""Parse inbound text message into structured DecisionDelta."""

from datetime import date, timedelta
from typing import Optional
import re
import os

from core.model import DecisionDelta
from llm.gemini import generate_text


def parse(text: str, today: date) -> DecisionDelta:
    """
    Parse inbound text message into structured decision.

    Uses Gemini with JSON schema mode. Falls back gracefully on errors.

    Args:
        text: Raw text message
        today: Today's date for relative date resolution

    Returns:
        DecisionDelta with extracted information and confidence score
    """
    try:
        return _parse_with_gemini(text, today)
    except Exception:
        return _parse_heuristic(text, today)


def _parse_with_gemini(text: str, today: date) -> DecisionDelta:
    """Parse using Gemini API with structured output."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _parse_heuristic(text, today)

    prompt = f"""Parse this text message into a spending decision.

Today is {today.isoformat()} ({today.strftime('%A')}).

Respond with JSON:
{{
    "kind": "one_time" or "recurring",
    "amount": number or null,
    "start_day": integer offset from today or null,
    "cadence_days": integer for recurring (null for one_time),
    "label": "short description",
    "confidence": 0.0 to 1.0
}}

Date resolution rules:
- "in December" (no day) → first day of that month, next occurrence
- "next month" → first day of next calendar month
- "next week" → today + 7
- "tomorrow" → 1
- "now", "today", no date → 0

Confidence:
- ≥ 0.85: explicit amount AND unambiguous kind/cadence
- 0.5–0.85: amount present but timing/kind needs default
- < 0.5: no amount, conflicting amounts, or not a spending decision

Message: {text}"""

    response = generate_text(prompt, max_output_tokens=256, json_mode=True)

    import json
    result = json.loads(response)

    # Post-model guards
    amount = result.get("amount")
    kind = result.get("kind", "unknown")
    cadence = result.get("cadence_days")
    confidence = result.get("confidence", 0.0)
    start_day = result.get("start_day")

    # Guard 1: amount null or <= 0 → low confidence
    if amount is None or amount <= 0:
        confidence = min(confidence, 0.49)

    # Guard 2: amount must appear in raw_text
    if amount and not _amount_in_text(amount, text):
        confidence = min(confidence, 0.49)

    # Guard 3: recurring without cadence → default 30, cap confidence at 0.7
    if kind == "recurring" and cadence is None:
        cadence = 30
        confidence = min(confidence, 0.7)

    # Guard 4: clamp start_day to [0, 730]
    if start_day is not None:
        start_day = max(0, min(730, start_day))
    # DecisionDelta is frozen; apply guards before constructing it.
    return DecisionDelta(kind=kind, amount=amount, start_day=start_day,
                         cadence_days=cadence, label=result.get("label", ""),
                         raw_text=text, confidence=confidence)


def _parse_heuristic(text: str, today: date) -> DecisionDelta:
    """Fallback heuristic parser when Gemini is unavailable."""
    text_lower = text.lower()

    # Extract amount
    amount = _extract_amount(text)

    # Detect kind and cadence
    is_recurring = any(
        word in text_lower
        for word in ['/mo', 'monthly', 'a month', '/wk', 'weekly', 'daily', '/yr', 'yearly', 'annual', 'every week', 'every day', 'every month']
    )
    kind = "recurring" if is_recurring else "one_time"

    cadence_days = None
    if is_recurring:
        if any(w in text_lower for w in ['/mo', 'monthly', 'a month', 'every month']):
            cadence_days = 30
        elif any(w in text_lower for w in ['/wk', 'weekly', 'every week']):
            cadence_days = 7
        elif 'biweekly' in text_lower or 'every two weeks' in text_lower:
            cadence_days = 14
        elif any(w in text_lower for w in ['/yr', 'yearly', 'annual']):
            cadence_days = 365
        elif 'daily' in text_lower or 'every day' in text_lower:
            cadence_days = 1

    # Extract date
    start_day = _extract_start_day(text, today)
    # No date mentioned → today, same rule as the Gemini prompt
    if start_day is None:
        start_day = 0

    # Calculate confidence
    confidence = _calculate_confidence(amount, kind, is_recurring, cadence_days)

    return DecisionDelta(
        kind=kind,
        amount=amount,
        start_day=start_day,
        cadence_days=cadence_days,
        label=text[:50],
        raw_text=text,
        confidence=confidence
    )


def _extract_amount(text: str) -> Optional[float]:
    """Extract dollar amount from text."""
    # Match patterns like $1400, $1,400, 1400, 1.4k, $1.5k
    pattern = r'\$?[\d,]+\.?\d*[kK]?|\$[\d,]+\.?\d*'
    matches = re.findall(pattern, text)

    if not matches:
        return None

    # Parse the first match
    amount_str = matches[0].lower().replace('$', '').replace(',', '')

    if 'k' in amount_str:
        try:
            return float(amount_str.replace('k', '')) * 1000
        except ValueError:
            return None

    try:
        return float(amount_str)
    except ValueError:
        return None


def _amount_in_text(amount: float, text: str) -> bool:
    """Check if the amount appears in the text (normalized)."""
    text_lower = text.lower()

    # Check exact formats
    amount_int = int(amount)
    amount_fmt1 = f"${amount_int}"
    amount_fmt2 = f"${amount_int:,}"
    amount_fmt3 = str(amount_int)

    if any(fmt in text_lower for fmt in [amount_fmt1, amount_fmt2, amount_fmt3]):
        return True

    # Check k format
    if amount >= 1000:
        k_val = amount / 1000
        k_fmt1 = f"{k_val:.1f}k"
        k_fmt2 = f"{k_val:.1f}K"
        if any(fmt in text_lower for fmt in [k_fmt1, k_fmt2]):
            return True

    return False


def _extract_start_day(text: str, today: date) -> Optional[int]:
    """Extract start date and return offset from today."""
    text_lower = text.lower()

    # Handle absolute dates
    months = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }

    for month_name, month_num in months.items():
        if month_name in text_lower:
            # Find next occurrence of this month
            year = today.year
            if month_num < today.month:
                year += 1
            target = date(year, month_num, 1)
            return (target - today).days

    # Handle relative dates
    if 'tomorrow' in text_lower:
        return 1
    elif 'next week' in text_lower:
        return 7
    elif 'next month' in text_lower:
        # First day of next month
        if today.month == 12:
            target = date(today.year + 1, 1, 1)
        else:
            target = date(today.year, today.month + 1, 1)
        return (target - today).days
    elif any(w in text_lower for w in ['today', 'now']):
        return 0

    return None


def _calculate_confidence(
    amount: Optional[float],
    kind: str,
    is_recurring: bool,
    cadence_days: Optional[int]
) -> float:
    """Calculate confidence score based on parsed data."""
    if amount is None or amount <= 0:
        return 0.3

    # Check if it's a clear decision
    if is_recurring and cadence_days is not None:
        return 0.85
    elif not is_recurring:
        return 0.85
    elif is_recurring and cadence_days is None:
        return 0.6

    return 0.7
