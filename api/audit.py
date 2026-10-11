"""Audit mode: "Where can I cut back?" -> top low-priority recurring expenses and what stopping them saves."""
from __future__ import annotations

import re

from core.audit import AuditResult
from core.model import CashflowModel, Decision, DecisionDelta
from llm.priority import classify_labels

_ASK = re.compile(
    r"\b(?:what|which|where)\b.*\b(?:cut|cancel|drop|trim|save|saving|savings)\b|"
    r"\bcut (?:back|down)\b|\breduce my (?:spending|expenses|bills|subscriptions)\b|"
    r"\b(?:unnecessary|non-?essential|low[- ]priority|optional) (?:expenses?|spending|bills|subscriptions)\b|"
    r"\b(?:stop|stopped|cancel|cancelled|canceled) (?:paying|spending|my (?:subscriptions|recurring))|"
    r"\bwithout my (?:subscriptions|recurring)|\bspending audit\b|\bbudget audit\b", re.I | re.S)
_DOLLARS = re.compile(r"\$\s?\d|\d\s*(?:dollars|bucks)\b", re.I)


def parse_audit(text: str) -> bool:
    """A cut-back question with no specific dollar amount (those are decisions or habits)."""
    return bool(_ASK.search(text)) and not _DOLLARS.search(text)


def priorities_for(model: CashflowModel) -> dict[str, str]:
    """obligation_id -> high | low. An obligation already marked essential stays high whatever the name says."""
    by_label = classify_labels([ob.label for ob in model.recurring])
    return {ob.obligation_id: "high" if ob.essential else by_label[ob.label] for ob in model.recurring}


def audit_decision(result: AuditResult, text: str) -> Decision:
    """The cuts as a steady weekly inflow, so the stored run's chart shows today vs. without them."""
    item = DecisionDelta(kind="recurring", amount=round(result.combined_yearly / 52, 2), start_day=0, cadence_days=7,
                         label="Audit savings", raw_text=text, confidence=1.0, direction="inflow")
    terms = {"audit": {"combined_yearly": result.combined_yearly,
                       "rows": [{"label": r.label, "yearly_savings": r.yearly_savings} for r in result.rows]}}
    return Decision(items=(item,), label="Audit savings", raw_text=text, confidence=1.0, terms=terms)


def _money(v: float) -> str:
    return f"${v:,.0f}" if float(v).is_integer() else f"${v:,.2f}"


def _every(days: float) -> str:
    return {1: "a day", 7: "a week", 14: "every two weeks", 30: "a month", 365: "a year"}.get(days, f"every {days:g} days")


def audit_response(result: AuditResult, years: float, baseline_rate: float, cut_rate: float, threshold: float = 0.0) -> str:
    lines = ["Where you could cut back (low-priority recurring spending):"]
    for i, r in enumerate(result.rows, 1):
        note = " (varies, so this is an average)" if r.variable else ""
        lines.append(f"{i}. {r.label}: {_money(r.amount)} {_every(r.cadence_days)}, about {_money(round(r.yearly_savings))} a year{note}")
    n = len(result.rows)
    what = "it" if n == 1 else "both" if n == 2 else f"all {n}"
    total = (f"Stopping {what} would save about {_money(round(result.combined_yearly))} a year "
             f"(roughly {_money(round(result.combined_yearly / 12))} a month).")
    horizon = f"{years:g} year{'s' if years != 1 else ''}"
    odds = (f"Chance your balance dips below {_money(threshold)} in the next {horizon}:\n"
            f"As things are: {round(baseline_rate * 100)}%\nWithout {'it' if n == 1 else 'them'}: {round(cut_rate * 100)}%")
    parts = ["\n".join(lines), total, odds]
    if result.kept:
        parts.append(f"I left these alone as essentials: {', '.join(result.kept)}.")
    parts.append("This is a forecast from simulations, not a guarantee.")
    return "\n\n".join(parts)
