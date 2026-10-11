"""Typical bank loan rates used to suggest financing. One fixed table for now.

Later, a user's own bank rates replace these: pass `rates=` to `financing_options`.
"""
from __future__ import annotations

PERSONAL_LOAN_APR = 0.12  # typical unsecured personal loan
DEFAULT_RATES: dict[str, float] = {"personal": PERSONAL_LOAN_APR, "mortgage": 0.07}
TERM_OPTIONS_MONTHS: tuple[int, ...] = (6, 12, 18, 24, 36, 48, 60)
