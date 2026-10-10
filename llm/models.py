"""Data models for the Gemini layer."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import date


@dataclass
class DecisionDelta:
    """Structured decision parsed from inbound text message."""
    kind: str  # "one_time" | "recurring"
    amount: Optional[float] = None
    start_day: Optional[int] = None  # offset in days from today; 0 = today
    cadence_days: Optional[int] = None  # None for one_time
    label: str = ""  # short human label
    raw_text: str = ""  # original message verbatim
    confidence: float = 0.0  # [0, 1]


@dataclass
class Claim:
    """Claim produced by Dev A's simulation.

    Frozen contract from 00-ARCHITECTURE.md:
    - kind: one of [baseline_breach_rate, breach_rate_with_delta, culprit_label,
                    culprit_marginal_contribution, culprit_amount, median_min_balance,
                    first_breach_week, paths_simulated]
    - value: the only legal source of any number in prose
    - unit: one of [probability, usd, week, count]
    - evidence: transaction IDs that support this claim
    """
    kind: str
    value: float
    unit: str = "usd"  # "probability" | "usd" | "week" | "count"
    claim_id: Optional[str] = None  # e.g., "c1", "c2"
    evidence: list[str] = field(default_factory=list)  # transaction IDs

    # Backwards compatibility: support old evidence_ids parameter
    @property
    def evidence_ids(self) -> list[str]:
        """Alias for evidence field for backwards compatibility."""
        return self.evidence

    @evidence_ids.setter
    def evidence_ids(self, value: list[str]) -> None:
        """Setter for backwards compatibility."""
        self.evidence = value


@dataclass
class Culprit:
    """Merchant or pattern the simulation identified."""
    label: str  # the merchant name


@dataclass
class ValidationResult:
    """Result of validating prose against claims."""
    passed: bool
    violations: list[str] = field(default_factory=list)  # human-readable violations
    prose: str = ""  # the prose that was checked
