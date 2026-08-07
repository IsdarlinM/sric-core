"""Security Research Intelligence Core (SRIC)."""

from .bitemporal import (
    BitemporalBounds,
    BitemporalRecord,
    TemporalConflict,
    detect_temporal_conflicts,
    select_bitemporal,
    supersede_record,
)
from .calibration import (
    ConfidenceBreakdown,
    ConfidenceSignal,
    SkepticReview,
    SkepticVerdict,
    brier_score,
    expected_calibration_error,
    score_confidence,
    skeptic_review,
)
from .merkle import (
    EvidenceDigest,
    MerkleProof,
    MerkleProofStep,
    ProofSide,
    build_merkle_proof,
    evidence_merkle_root,
    merkle_root,
    verify_merkle_proof,
)
from .models import ClaimStatus, Confidence, EvidenceReference, FindingStatus
from .source_quality import (
    SourceAuthority,
    SourceIndependenceReport,
    SourceProfile,
    resolve_source_independence,
)

__all__ = [
    "BitemporalBounds",
    "BitemporalRecord",
    "ClaimStatus",
    "Confidence",
    "ConfidenceBreakdown",
    "ConfidenceSignal",
    "EvidenceDigest",
    "EvidenceReference",
    "FindingStatus",
    "MerkleProof",
    "MerkleProofStep",
    "ProofSide",
    "SkepticReview",
    "SkepticVerdict",
    "SourceAuthority",
    "SourceIndependenceReport",
    "SourceProfile",
    "TemporalConflict",
    "brier_score",
    "build_merkle_proof",
    "detect_temporal_conflicts",
    "evidence_merkle_root",
    "expected_calibration_error",
    "merkle_root",
    "resolve_source_independence",
    "score_confidence",
    "select_bitemporal",
    "skeptic_review",
    "supersede_record",
    "verify_merkle_proof",
]
__version__ = "0.4.1"
