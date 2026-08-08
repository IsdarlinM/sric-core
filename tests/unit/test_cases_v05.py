from __future__ import annotations

import pytest
from pydantic import ValidationError

from sric.cases import (
    CaseArtifact,
    CaseArtifactType,
    SentinelCase,
    ValidationRecipe,
    claim_fingerprint,
    evidence_adequacy,
)
from sric.models import ActionClass, ClaimStatus


def test_claim_fingerprint_is_deterministic() -> None:
    left = claim_fingerprint(
        claim_type="authorization",
        subject="actor:a",
        predicate="CAN_READ",
        object_value="resource:1",
        context={"tenant": "t1"},
    )
    right = claim_fingerprint(
        claim_type="authorization",
        subject="actor:a",
        predicate="can_read",
        object_value="resource:1",
        context={"tenant": "t1"},
    )
    assert left == right
    assert left.startswith("claim:")


def test_validated_artifact_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        CaseArtifact(
            artifact_id="a1",
            artifact_type=CaseArtifactType.FINDING,
            source_tool="authtwin",
            source_ref="finding:1",
            status=ClaimStatus.VALIDATED,
        )


def test_mutating_recipe_requires_human_approval() -> None:
    with pytest.raises(ValidationError):
        ValidationRecipe(
            recipe_id="r1",
            artifact_id="a1",
            action_class=ActionClass.MUTATING_REVERSIBLE,
            target="https://example.invalid/resource/1",
            method="PATCH",
            deterministic_success="response status is 200 and state is restored",
        )


def test_case_rejects_dangling_recipe_and_scores_evidence() -> None:
    artifact = CaseArtifact(
        artifact_id="a1",
        artifact_type=CaseArtifactType.HYPOTHESIS,
        source_tool="trustboundary",
        source_ref="candidate:1",
        status=ClaimStatus.HYPOTHESIS,
        evidence_ids=["ev-1"],
    )
    recipe = ValidationRecipe(
        recipe_id="r1",
        artifact_id="a1",
        action_class=ActionClass.READ_ONLY_SAFE,
        target="https://example.invalid/",
        method="GET",
        deterministic_success="expected identity is observed",
        required_evidence=["ev-1", "ev-2"],
    )
    case = SentinelCase(case_id="case-1", title="Example", artifacts=[artifact], validation_recipes=[recipe])
    assert case.unresolved_artifacts() == ["a1"]
    assert evidence_adequacy(case.artifacts, recipe.required_evidence) == 0.5
