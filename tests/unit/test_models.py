import pytest
from sric.models import Claim, ClaimStatus, Confidence


def conf() -> Confidence:
    return Confidence(score=0.8, rationale="test")


def test_validated_claim_requires_evidence() -> None:
    with pytest.raises(ValueError):
        Claim(
            claim_id="C1",
            claim="x",
            status=ClaimStatus.VALIDATED,
            confidence=conf(),
            evidence_ids=[],
            source="test",
        )
