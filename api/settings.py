"""Adjustable assumptions (tax, interest rates, simulation size), read from Supabase.

`settings` holds the shared values; `customer_settings` holds per-person overrides for the things that
genuinely differ between people (PER_CUSTOMER: tax share and loan rates). Simulation settings are shared on
purpose, so every person's odds come from the same size and length of simulation.

Code constants are the defaults and the fallback: with no DATABASE_URL, with SETTINGS_SOURCE=code, or if the
database is unreachable, the API behaves exactly as before. Values are cached briefly so a question never
waits on the database more than once a minute, and every value is range-checked so a typo in the table
can't produce a 50,000-path simulation or a 300% tax rate.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, fields, replace

from core.feasible import SAFE_BREACH_RATE
from core.income import NET_FACTOR
from core.rates import DEFAULT_RATES

logger = logging.getLogger(__name__)

CACHE_SECONDS = 60


@dataclass(frozen=True)
class Settings:
    income_net_factor: float = NET_FACTOR
    personal_loan_apr: float = DEFAULT_RATES["personal"]
    mortgage_apr: float = DEFAULT_RATES["mortgage"]
    safe_breach_rate: float = SAFE_BREACH_RATE
    simulation_paths: int = 500
    horizon_weeks: int = 104
    breach_threshold: float = 0.0

    @property
    def rates(self) -> dict[str, float]:
        return {"personal": self.personal_loan_apr, "mortgage": self.mortgage_apr}


# key -> (unit, description, min, max). Seeded into the table by data/supabase_setup.py.
SPEC: dict[str, tuple[str, str, float, float]] = {
    "income_net_factor": ("ratio", "Share of gross pay, raises and bonuses kept after taxes "
                          "(0.78 = assume 22% goes to taxes).", 0.4, 1.0),
    "personal_loan_apr": ("rate", "Typical personal-loan APR used to suggest financing (0.12 = 12%).", 0.0, 0.6),
    "mortgage_apr": ("rate", "Typical mortgage APR (0.07 = 7%).", 0.0, 0.3),
    "safe_breach_rate": ("probability", "Odds of dipping below the threshold that count as safe; above this, "
                         "the app suggests a safer time and financing (0.10 = 10%).", 0.01, 0.5),
    "simulation_paths": ("count", "How many possible futures each question simulates.", 100, 2000),
    "horizon_weeks": ("weeks", "How far ahead each simulation looks (104 = 2 years).", 13, 260),
    "breach_threshold": ("usd", "Balance counted as running short (0 = below $0).", -5000, 100000),
}
DEFAULTS = Settings()

# Keys that may differ per person, with the realistic range data/supabase_setup.py draws each person's value
# from (and the step it rounds to). Everything else is shared by all customers.
PER_CUSTOMER: dict[str, tuple[float, float, float]] = {
    "income_net_factor": (0.72, 0.84, 0.01),     # 16-28% of income to taxes
    "mortgage_apr": (0.06, 0.0775, 0.00125),      # 6%-7.75%, in 1/8-point steps
    "personal_loan_apr": (0.09, 0.18, 0.0025),    # 9%-18%, depends on credit
}


def coerce(raw: dict[str, float]) -> Settings:
    """Apply in-range values from the table; anything missing, unknown or out of range keeps its default."""
    values = {}
    for f in fields(Settings):
        if f.name not in raw:
            continue
        lo, hi = SPEC[f.name][2], SPEC[f.name][3]
        try:
            value = float(raw[f.name])
        except (TypeError, ValueError):
            logger.warning("setting_invalid key=%s", f.name)
            continue
        if not lo <= value <= hi:
            logger.warning("setting_out_of_range key=%s", f.name)
            continue
        values[f.name] = int(value) if f.type in ("int", int) else value
    return replace(DEFAULTS, **values)


class SettingsSource:
    """Callable returning the current Settings (optionally for one customer); reads Supabase at most once
    per CACHE_SECONDS."""

    def __init__(self, database_url: str | None = None, *, cache_seconds: float = CACHE_SECONDS):
        enabled = os.getenv("SETTINGS_SOURCE", "supabase") != "code"
        self.database_url = (database_url if database_url is not None else os.getenv("DATABASE_URL", "")) if enabled else ""
        self.cache_seconds = cache_seconds
        self._shared: dict = {}
        self._customers: dict[str, dict] = {}
        self._loaded_at = float("-inf")
        self._lock = threading.Lock()

    def __call__(self, customer_id: str | None = None) -> Settings:
        if not self.database_url:
            return DEFAULTS
        with self._lock:
            if time.monotonic() - self._loaded_at >= self.cache_seconds:
                self._refresh()
                self._loaded_at = time.monotonic()
            # Only per-person keys may be overridden; simulation settings always come from the shared table.
            own = {k: v for k, v in self._customers.get(customer_id or "", {}).items() if k in PER_CUSTOMER}
            return coerce({**self._shared, **own})

    def _refresh(self) -> None:
        try:
            import psycopg
            with psycopg.connect(self.database_url, connect_timeout=5) as conn:
                shared = dict(conn.execute("select key, value from public.settings").fetchall())
                customers: dict[str, dict] = {}
                if conn.execute("select to_regclass('public.customer_settings')").fetchone()[0]:
                    for cid, key, value in conn.execute("select customer_id, key, value from public.customer_settings"):
                        customers.setdefault(cid, {})[key] = value
            self._shared, self._customers = shared, customers
        except Exception as exc:  # unreachable or not set up yet: keep the last good values
            logger.warning("settings_load_failed error_type=%s", type(exc).__name__)
