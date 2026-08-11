import pytest
from sric.models import Claim, ClaimStatus, Confidence
from sric.workspace import Workspace


def test_workspace_initialize_bootstraps_empty_directory(tmp_path):
    workspace = Workspace.initialize(tmp_path)
    assert workspace.root == tmp_path.resolve()
    assert (workspace.root / "workspace.json").is_file()
    assert Workspace.initialize(tmp_path).root == workspace.root


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
