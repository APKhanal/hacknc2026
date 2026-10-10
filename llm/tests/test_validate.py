"""Tests for prose validation against claims."""

import pytest
from llm.models import Claim, Culprit, ValidationResult
from llm.validate import validate, NumberValidator


class TestNumericTrace:
    """Check 1: Every number must match a claim."""

    def test_valid_dollar_amount(self):
        """Valid dollar amounts should pass."""
        culprit = Culprit(label="Netflix")
        claims = [Claim(kind="amount", value=15.99, evidence=[])]
        prose = "Netflix costs $15.99 per month."

        result = validate(prose, claims, culprit)
        assert result.passed

    def test_orphan_number_fails(self):
        """Numbers not in claims should fail."""
        culprit = Culprit(label="Gym")
        claims = [Claim(kind="amount", value=65.0, evidence=[])]
        prose = "Gym costs $165 per month."  # $165 not in claims

        result = validate(prose, claims, culprit)
        assert not result.passed
        assert any("orphan" in v.lower() for v in result.violations)

    def test_percent_normalization(self):
        """Percentages should normalize: 0.27 matches 27%."""
        culprit = Culprit(label="Flight")
        claims = [Claim(kind="probability", value=0.27, evidence=[])]
        prose = "There's a 27% chance you can afford this flight."

        result = validate(prose, claims, culprit)
        assert result.passed

    def test_dollar_formats_match(self):
        """$142 should match 142.00 within tolerance."""
        culprit = Culprit(label="Book")
        claims = [Claim(kind="cost", value=142.00, evidence=[])]
        prose = "The book costs $142."

        result = validate(prose, claims, culprit)
        assert result.passed

    def test_k_suffix_extraction(self):
        """1.4k should extract and match 1400."""
        culprit = Culprit(label="Laptop")
        claims = [Claim(kind="amount", value=1400.0, evidence=[])]
        prose = "A laptop costs 1.4k dollars."

        result = validate(prose, claims, culprit)
        assert result.passed

    def test_spelled_out_number_rejected(self):
        """Spelled-out numbers should be flagged as violations."""
        culprit = Culprit(label="Car")
        claims = [Claim(kind="probability", value=0.5, evidence=[])]
        prose = "There's about a fifty percent chance."

        result = validate(prose, claims, culprit)
        assert not result.passed
        assert any("spelled" in v.lower() or "fifty" in v.lower() for v in result.violations)

    def test_negative_amount(self):
        """Negative amounts should extract correctly."""
        culprit = Culprit(label="Refund")
        claims = [Claim(kind="refund", value=-50.0, evidence=[])]
        prose = "Your Refund could be -$50."

        result = validate(prose, claims, culprit)
        assert result.passed

    def test_multiple_numbers_all_valid(self):
        """All numbers in prose must be in claims."""
        culprit = Culprit(label="Trip")
        claims = [
            Claim(kind="flight", value=1400.0, evidence=[]),
            Claim(kind="hotel", value=200.0, evidence=[])
        ]
        prose = "Your Trip costs $1400 flight and $200 hotel per night."

        result = validate(prose, claims, culprit)
        assert result.passed


class TestEvidenceExistence:
    """Check 2: Transaction IDs must resolve."""

    def test_evidence_ids_resolve(self):
        """Valid evidence IDs should pass."""
        def mock_resolver(txn_id):
            return txn_id in ["txn_001", "txn_002"]

        culprit = Culprit(label="Amazon")
        claims = [
            Claim(kind="amount", value=50.0, evidence=["txn_001", "txn_002"])
        ]
        prose = "Your Amazon purchase for $50 was from txn_001."

        result = validate(prose, claims, culprit, txn_resolver=mock_resolver)
        assert result.passed

    def test_unresolvable_evidence_id(self):
        """Unresolvable transaction IDs should fail."""
        def mock_resolver(txn_id):
            return txn_id in ["txn_001"]

        culprit = Culprit(label="Store")
        claims = [
            Claim(kind="amount", value=50.0, evidence=["txn_999"])  # doesn't exist
        ]
        prose = "Your store purchase was $50."

        result = validate(prose, claims, culprit, txn_resolver=mock_resolver)
        assert not result.passed
        assert any("unresolvable" in v.lower() for v in result.violations)

    def test_no_resolver_skips_check(self):
        """If no resolver provided, evidence check is skipped."""
        culprit = Culprit(label="Shop")
        claims = [
            Claim(kind="amount", value=50.0, evidence=["txn_missing"])
        ]
        prose = "Shop purchase is $50."

        result = validate(prose, claims, culprit, txn_resolver=None)
        # Should pass on numeric check, evidence check skipped
        assert result.passed or not any("unresolvable" in v.lower() for v in result.violations)


class TestCulpritConsistency:
    """Check 3: Culprit must be named correctly."""

    def test_culprit_present(self):
        """Culprit name must appear in prose."""
        culprit = Culprit(label="Netflix")
        claims = [Claim(kind="amount", value=15.99, evidence=[])]
        prose = "Netflix charges $15.99 per month."

        result = validate(prose, claims, culprit)
        assert result.passed

    def test_culprit_missing(self):
        """Missing culprit should fail."""
        culprit = Culprit(label="Netflix")
        claims = [Claim(kind="amount", value=15.99, evidence=[])]
        prose = "This streaming service costs $15.99 per month."

        result = validate(prose, claims, culprit)
        assert not result.passed
        assert any("culprit" in v.lower() or "netflix" in v.lower() for v in result.violations)

    def test_culprit_case_insensitive(self):
        """Culprit matching should be case-insensitive."""
        culprit = Culprit(label="Netflix")
        claims = [Claim(kind="amount", value=15.99, evidence=[])]
        prose = "NETFLIX costs $15.99."

        result = validate(prose, claims, culprit)
        assert result.passed


class TestAdversarial:
    """Seeded adversarial test: fabricated numbers should be rejected."""

    def test_fabricated_orphan_number(self):
        """Hand-written prose with plausible but fabricated number."""
        culprit = Culprit(label="Spotify")
        claims = [Claim(kind="amount", value=9.99, evidence=[])]

        # This prose contains a plausible but fabricated number: $11.99
        prose = "Spotify costs $9.99 per month, but you're looking at plans around $11.99."

        result = validate(prose, claims, culprit)
        assert not result.passed, "Should reject fabricated $11.99"
        assert any("$11.99" in v or "11.99" in v for v in result.violations)

    def test_validator_rejects_malformed_prose(self):
        """Prose that tries to sneak in computed numbers."""
        culprit = Culprit(label="Gym")
        claims = [
            Claim(kind="monthly", value=65.0, evidence=[]),
            Claim(kind="commitment_months", value=12.0, evidence=[])
        ]

        # This prose violates the rule: it computes $780 (65 * 12)
        prose = "Gym is $65/mo, so a 12-month commitment is $780."

        result = validate(prose, claims, culprit)
        assert not result.passed, "Should reject computed $780"


class TestValidationIntegration:
    """Test validation with realistic scenarios."""

    def test_valid_complete_response(self):
        """A well-formed response should pass all checks."""
        culprit = Culprit(label="Flight")
        claims = [
            Claim(kind="probability", value=0.85, evidence=[]),
            Claim(kind="amount", value=1400.0, evidence=[])
        ]
        prose = "There's an 85% chance you can afford this Flight for $1400."

        result = validate(prose, claims, culprit)
        assert result.passed

    def test_multiple_violations_collected(self):
        """All violations should be reported at once."""
        culprit = Culprit(label="Car")
        claims = [Claim(kind="amount", value=25000.0, evidence=[])]
        prose = "A car costs about $35000 but Bike is only $200."

        result = validate(prose, claims, culprit)
        assert not result.passed
        # Should have violations for: orphan $35000, orphan $200, missing culprit
        assert len(result.violations) >= 1
