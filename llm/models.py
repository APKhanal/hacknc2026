"""Import canonical models from core.

This module re-exports the frozen contract models from core.model
to avoid isinstance() failures in api/pipeline.py.
"""

from core.model import DecisionDelta, Claim, Culprit  # noqa: F401
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of validating prose against claims."""
    passed: bool
    violations: list[str] = field(default_factory=list)
    prose: str = ""
