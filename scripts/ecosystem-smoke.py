#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone

from authtwin.coverage import ResourceSensitivity, UnknownAuthorizationCell, ValidationCost
from authtwin.research import build_validation_plan
from exposuredna.eras import TemporalRelationshipClaim, relationship_at
from exposuredna.resolution import RelationshipType
from fossilscope.planning import CurrentExposureState, ReobservationCandidate, plan_reobservation
from reprosec.research_context import CapsuleResearchContext, ScopeSnapshot, ToolProvenanceRecord
from sric.cases import CaseArtifact, CaseArtifactType, SentinelCase, ValidationRecipe
from sric.models import ActionClass, ClaimStatus
from trustboundary.invariants import TrustInvariant, TrustInvariantKind, evaluate_trust_invariant
from trustboundary.models import Transition

UTC = timezone.utc


def main() -> int:
    case = SentinelCase(
        case_id="case-ecosystem-smoke",
        title="Sentinel Forge 0.5 contract smoke",
        artifacts=[
            CaseArtifact(
                artifact_id="artifact-auth-gap",
                artifact_type=CaseArtifactType.HYPOTHESIS,
                source_tool="authtwin",
                source_ref="cell:auth-1",
                status=ClaimStatus.UNKNOWN,
                evidence_ids=["ev-observed-request"],
            )
        ],
        validation_recipes=[
            ValidationRecipe(
                recipe_id="recipe-read",
                artifact_id="artifact-auth-gap",
                action_class=ActionClass.READ_ONLY_SAFE,
                target="https://example.test/resource/1",
                method="GET",
                deterministic_success="expected authorization decision is observed",
                required_evidence=["ev-observed-request"],
            )
        ],
    )

    context = CapsuleResearchContext(
        sentinel_case_id=case.case_id,
        scope_snapshot=ScopeSnapshot(
            snapshot_id="scope-1",
            allowed_hosts=["example.test"],
            source="ecosystem-smoke",
        ),
        validation_recipes=case.validation_recipes,
        tool_provenance=[
            ToolProvenanceRecord(
                tool="sric-core",
                version="0.5.0",
                component="ecosystem-smoke",
                source_ref=case.case_id,
            )
        ],
    )
    if len(context.sha256()) != 64:
        raise RuntimeError("ReproSec research context digest is invalid")

    auth_plans = build_validation_plan(
        [
            UnknownAuthorizationCell(
                cell_id="auth-1",
                actor_id="actor-a",
                tenant_id="tenant-a",
                resource_id="document-1",
                operation="READ",
                resource_sensitivity=ResourceSensitivity.CONFIDENTIAL,
                crosses_tenant_boundary=True,
                validation_cost=ValidationCost.READ_ONLY_SAFE,
                equivalence_class="documents",
            ),
            UnknownAuthorizationCell(
                cell_id="auth-2",
                actor_id="actor-a",
                tenant_id="tenant-a",
                resource_id="document-2",
                operation="READ",
                resource_sensitivity=ResourceSensitivity.CONFIDENTIAL,
                crosses_tenant_boundary=True,
                validation_cost=ValidationCost.READ_ONLY_SAFE,
                equivalence_class="documents",
            ),
        ]
    )
    if len(auth_plans) != 1 or auth_plans[0].status is not ClaimStatus.UNKNOWN:
        raise RuntimeError("AuthTwin coverage planning contract failed")

    fossil_plans = plan_reobservation(
        [
            ReobservationCandidate(
                asset_id="legacy-api",
                target="https://legacy.example.test/api",
                exposure_state=CurrentExposureState.REACHABILITY_UNKNOWN,
                current_reference=True,
                auth_relevance=True,
                evidence_ids=["ev-historical"],
            )
        ]
    )
    if not fossil_plans or fossil_plans[0].mode.value != "PASSIVE":
        raise RuntimeError("FossilScope passive planning contract failed")

    trust_result = evaluate_trust_invariant(
        TrustInvariant(
            invariant_id="trust-1",
            kind=TrustInvariantKind.VERIFIED_IDENTITY,
            target_node_id="service",
            data_type="identity",
        ),
        [
            Transition(
                transition_id="transition-1",
                source_node_id="gateway",
                target_node_id="service",
                data_type="identity",
                verified=False,
                evidence_ids=["ev-trust"],
            )
        ],
    )
    if trust_result.status is not ClaimStatus.HYPOTHESIS:
        raise RuntimeError("TrustBoundary invariant contract failed")

    relationship = TemporalRelationshipClaim(
        relationship_id="ownership-2022",
        subject_id="org-a",
        object_id="legacy.example.test",
        relationship_type=RelationshipType.OWNS,
        valid_from=datetime(2021, 1, 1, tzinfo=UTC),
        valid_to=datetime(2023, 12, 31, tzinfo=UTC),
        status=ClaimStatus.INFERRED,
        evidence_ids=["ev-ownership"],
    )
    current = relationship_at(relationship, datetime(2026, 8, 8, tzinfo=UTC))
    if current.active or current.status is not ClaimStatus.UNKNOWN:
        raise RuntimeError("Exposure DNA temporal-boundary contract failed")

    print("[PASS] Sentinel Forge 0.5 ecosystem contract smoke")
    print(f"case={case.case_id} context_sha256={context.sha256()}")
    print(f"authtwin_plans={len(auth_plans)} fossilscope_plans={len(fossil_plans)}")
    print(f"trust_status={trust_result.status.value} ownership_now={current.status.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
