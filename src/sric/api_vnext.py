from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .api import create_app as create_base_app
from .bitemporal import (
    BitemporalRecord,
    detect_temporal_conflicts,
    select_bitemporal,
)
from .calibration import (
    ConfidenceSignal,
    brier_score,
    expected_calibration_error,
    score_confidence,
    skeptic_review,
)
from .merkle import EvidenceDigest, build_merkle_proof, evidence_merkle_root
from .source_quality import SourceProfile, resolve_source_independence


class ConfidenceAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signals: list[ConfidenceSignal]
    base_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    maximum: float = Field(default=0.95, ge=0.0, le=1.0)
    alternative_explanations: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    missing_required_evidence: list[str] = Field(default_factory=list)


class CalibrationMetricsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    probabilities: list[float]
    outcomes: list[int]
    bins: int = Field(default=10, ge=2, le=100)


class BitemporalQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[BitemporalRecord]
    valid_at: datetime
    known_at: datetime
    entity_id: str | None = None
    fact_type: str | None = None


class SourceIndependenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[SourceProfile]


class EvidenceMerkleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: list[EvidenceDigest]
    prove_evidence_id: str | None = None


router = APIRouter(prefix="/api/v1/evidence-native", tags=["evidence-native"])


@router.post("/confidence/analyze")
async def confidence_analyze(
    request: ConfidenceAnalysisRequest,
) -> dict[str, object]:
    breakdown = score_confidence(
        request.signals,
        base_confidence=request.base_confidence,
        maximum=request.maximum,
    )
    review = skeptic_review(
        breakdown,
        alternative_explanations=request.alternative_explanations,
        counter_evidence_ids=request.counter_evidence_ids,
        missing_required_evidence=request.missing_required_evidence,
    )
    return {
        "breakdown": breakdown.model_dump(mode="json"),
        "skeptic_review": review.model_dump(mode="json"),
        "validated_finding_created": False,
    }


@router.post("/confidence/calibration")
async def confidence_calibration(
    request: CalibrationMetricsRequest,
) -> dict[str, object]:
    return {
        "brier_score": brier_score(request.probabilities, request.outcomes),
        "expected_calibration_error": expected_calibration_error(
            request.probabilities,
            request.outcomes,
            bins=request.bins,
        ),
        "sample_count": len(request.probabilities),
    }


@router.post("/bitemporal/query")
async def bitemporal_query(request: BitemporalQueryRequest) -> dict[str, object]:
    selected = select_bitemporal(
        request.records,
        valid_at=request.valid_at,
        known_at=request.known_at,
        entity_id=request.entity_id,
        fact_type=request.fact_type,
    )
    conflicts = detect_temporal_conflicts(
        request.records,
        valid_at=request.valid_at,
        known_at=request.known_at,
    )
    return {
        "records": [item.model_dump(mode="json") for item in selected],
        "conflicts": [item.model_dump(mode="json") for item in conflicts],
        "future_knowledge_used": False,
    }


@router.post("/sources/independence")
async def source_independence(
    request: SourceIndependenceRequest,
) -> dict[str, object]:
    report = resolve_source_independence(request.sources)
    return report.model_dump(mode="json")


@router.post("/integrity/merkle")
async def integrity_merkle(request: EvidenceMerkleRequest) -> dict[str, object]:
    if not request.evidence:
        raise HTTPException(400, "at least one evidence digest is required")
    ordered = sorted(request.evidence, key=lambda item: item.evidence_id)
    root = evidence_merkle_root(ordered)
    response: dict[str, object] = {
        "root_sha256": root,
        "evidence_count": len(ordered),
        "proof": None,
        "truthfulness_proved": False,
    }
    if request.prove_evidence_id is not None:
        index = next(
            (
                position
                for position, item in enumerate(ordered)
                if item.evidence_id == request.prove_evidence_id
            ),
            None,
        )
        if index is None:
            raise HTTPException(404, "prove_evidence_id is not present")
        proof = build_merkle_proof(
            [item.canonical_bytes() for item in ordered],
            index,
        )
        response["proof"] = proof.model_dump(mode="json")
    return response


def create_app() -> FastAPI:
    app = create_base_app()
    app.include_router(router)
    return app
