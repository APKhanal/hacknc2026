"""Orchestration: render with validation, retry once, then fall back to template."""

from typing import Union, Optional, Callable
from llm.models import Claim, Culprit, ValidationResult
from llm.render import render
from llm.validate import validate
from llm.template import template


# Path counter for demonstrating Gemini actually fires
_path_stats = {
    "render_first_try": 0,
    "render_retry": 0,
    "template": 0,
}


def get_path_stats() -> dict:
    """Get current path statistics (for demo/judging)."""
    return _path_stats.copy()


def reset_path_stats() -> None:
    """Reset path statistics."""
    global _path_stats
    _path_stats = {
        "render_first_try": 0,
        "render_retry": 0,
        "template": 0,
    }


def answer(
    claims: list[Claim],
    culprit: Culprit,
    txn_resolver: Optional[Callable[[str], bool]] = None
) -> Union[str, list[str]]:
    """
    Entry point for B and D to get an answer about claims.

    Orchestrates: render → validate → retry → template
    Always succeeds; never raises.

    Args:
        claims: List of claims from simulation
        culprit: The identified culprit/merchant
        txn_resolver: Optional function to check if transaction IDs exist

    Returns:
        Natural prose (validated or templated)
    """
    violations_log: list[str] = []

    try:
        # Step 1: Try render
        prose = render(claims, culprit)

        # Step 2: Validate
        result = validate(prose, claims, culprit, txn_resolver)
        violations_log = result.violations

        if result.passed:
            _path_stats["render_first_try"] += 1
            _log_path("render_first_try", violations_log)
            return prose

        # Step 3: Retry render with feedback
        feedback_prose = render(claims, culprit, violation_feedback=result.violations)

        # Step 4: Validate retry
        retry_result = validate(feedback_prose, claims, culprit, txn_resolver)
        violations_log = retry_result.violations

        if retry_result.passed:
            _path_stats["render_retry"] += 1
            _log_path("render_retry", violations_log)
            return feedback_prose

    except Exception as e:
        # Any exception: fall back to template
        pass

    # Step 5: Fall back to template
    _path_stats["template"] += 1
    _log_path("template", violations_log)
    return template(claims, culprit)


def _log_path(path: str, violations: list[str]) -> None:
    """Log which path was taken (for demo/debugging)."""
    print(f"[LLM] Path: {path}")
    if violations:
        print(f"[LLM] Violations encountered: {len(violations)}")
        for v in violations:
            print(f"  - {v}")
