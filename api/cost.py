"""Habit-cost mode: "How much would I lose per year if I got a coffee 2-3 times a week at $7?"

Deterministic. The text gives an amount and a frequency (maybe a range); the yearly cost is plain
arithmetic. The habit is then also run through the simulation as a weekly expense so the reply can
say whether the user can carry it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.income import current_annual_income
from core.model import CashflowModel, Decision, DecisionDelta

PER_YEAR = {"day": 365, "week": 52, "month": 12, "year": 1}
_WORDS = {"once": 1, "twice": 2, "thrice": 3}
_UNIT = r"(day|week|month|year)"
_ASK = re.compile(r"how much\b.*?\b(?:cost\w*|los\w+|spen[dt]\w*|wast\w+|pa(?:y|ying|id)|burn\w*|sav\w+)\b|"
                  r"what(?:'s| is| would be) the (?:yearly |annual )?cost|cost me|add up|per year|a year|"
                  r"annually|yearly|each year|over a year", re.I | re.S)
_MONEY = re.compile(r"\$\s?(\d+(?:,\d{3})*(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:dollars|bucks)\b", re.I)
_RANGE = re.compile(rf"(\d+)\s*(?:-|–|to)\s*(\d+)\s*(?:x|times?)?\s*(?:a|per|each|/|every)\s*{_UNIT}", re.I)
_TIMES = re.compile(rf"(\d+|once|twice|thrice)\s*(?:x|times?)?\s*(?:a|per|each|/|every)\s*{_UNIT}", re.I)
_QTY = re.compile(r"(?<![\w.$])(\d+(?:\.\d+)?)\s+(?!(?:times?|x|dollars?|bucks|years?|months?|weeks?|days?|percent|%)\b)[a-z]", re.I)
_EVERY = re.compile(r"\b(daily|every day|weekly|every week|monthly|every month|yearly|annually)\b", re.I)
_PER = re.compile(rf"(?:/|\ba\b|\bper\b|\beach\b|\bevery\b)\s*{_UNIT}", re.I)
_SIMPLE = {"daily": "day", "every day": "day", "weekly": "week", "every week": "week",
           "monthly": "month", "every month": "month", "yearly": "year", "annually": "year"}


@dataclass(frozen=True)
class HabitCost:
    amount: float
    low_per_period: float
    high_per_period: float
    period: str  # day | week | month | year
    low_year: float
    high_year: float

    @property
    def mid_year(self) -> float:
        return (self.low_year + self.high_year) / 2

    @property
    def is_range(self) -> bool:
        return self.low_per_period != self.high_per_period


def _count(token: str) -> float:
    return float(_WORDS[token.lower()]) if token.lower() in _WORDS else float(token)


def parse_habit(text: str) -> HabitCost | None:
    """None unless the text is a how-much-per-year question with one amount and a frequency."""
    if not _ASK.search(text):
        return None
    amounts = [float((m.group(1) or m.group(2)).replace(",", "")) for m in _MONEY.finditer(text)]
    if len(amounts) != 1 or amounts[0] <= 0:
        return None
    text = _MONEY.sub(" ", text)  # the price is not a count
    if (m := _RANGE.search(text)):
        low, high, period = float(m[1]), float(m[2]), m[3].lower()
        if low > high:
            low, high = high, low
    elif (m := _TIMES.search(text)):
        low = high = _count(m[1])
        period = m[2].lower()
    elif (m := _EVERY.search(text)):
        period = _SIMPLE[m[1].lower()]
        qty = _QTY.findall(text)  # "1 pack of cigarettes every day"
        low = high = float(qty[0]) if len(qty) == 1 else 1.0
    elif (found := [p.lower() for p in _PER.findall(text)]):
        # "$15 a month ... per year": the habit's own period beats the asked-about "per year"
        period = next((p for p in found if p != "year"), "year")
        qty = _QTY.findall(text)  # "2 packs a day": the quantity multiplies the unit price
        low = high = float(qty[0]) if len(qty) == 1 else 1.0
    if low is None or not 0 < low <= high <= 1000:
        return None
    return HabitCost(amounts[0], low, high, period, amounts[0] * low * PER_YEAR[period],
                     amounts[0] * high * PER_YEAR[period])


def habit_decision(habit: HabitCost, text: str) -> Decision:
    """The typical (midpoint) habit as a weekly expense, for the odds."""
    weekly = habit.mid_year / 52
    item = DecisionDelta(kind="recurring", amount=round(weekly, 2), start_day=0, cadence_days=7,
                         label="Habit spending", raw_text=text, confidence=1.0)
    return Decision(items=(item,), label="Habit spending", raw_text=text, confidence=1.0,
                    terms={"habit": {"amount": habit.amount, "period": habit.period,
                                     "low_year": habit.low_year, "high_year": habit.high_year}})


def _money(v: float) -> str:
    return f"${v:,.0f}"


def _times(habit: HabitCost) -> str:
    if habit.low_per_period == habit.high_per_period == 1:
        return f"once a {habit.period}"
    n = (f"{habit.low_per_period:g}-{habit.high_per_period:g}" if habit.is_range else f"{habit.low_per_period:g}")
    return f"{n} time{'s' if habit.high_per_period != 1 else ''} a {habit.period}"


def habit_response(habit: HabitCost, model: CashflowModel, breach_rate: float, baseline_rate: float,
                   horizon_years: float, threshold: float = 0.0) -> str:
    cost = (f"{_money(habit.low_year)}-{_money(habit.high_year)} a year" if habit.is_range
            else f"{_money(habit.low_year)} a year")
    lines = [f"Habit check: {_times(habit)} at {_money(habit.amount) if habit.amount.is_integer() else f'${habit.amount:,.2f}'} "
             f"adds up to about {cost}."]
    detail = f"That's roughly {_money(habit.mid_year / 12)} a month"
    income = current_annual_income(model)
    if income > 0:
        detail += f", about {habit.mid_year / income * 100:.1f}% of your yearly take-home"
    detail += f", and about {_money(habit.mid_year * 5)} over 5 years."
    lines.append(detail)
    if breach_rate <= baseline_rate + 0.01:
        verdict = "Easily affordable: it doesn't change your odds of running short."
    elif breach_rate < 0.2:
        verdict = "Affordable, but it does nudge your odds of running short."
    else:
        verdict = "It's small, but your cash is tight enough that it tips you toward running short."
    years = f"{horizon_years:g} year{'s' if horizon_years != 1 else ''}"
    lines.append(f"{verdict}\n\nChance your balance dips below {_money(threshold)} in the next {years}:\n"
                 f"With it: {round(breach_rate * 100)}%\nWithout it: {round(baseline_rate * 100)}%")
    lines.append("This is a forecast from simulations using the midpoint of your estimate, not a guarantee.")
    return "\n\n".join(lines)
