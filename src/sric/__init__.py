"""Security Research Intelligence Core (SRIC)."""

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
from .models import ClaimStatus, Confidence, EvidenceReference, FindingStatus

__all__ = [
    "ClaimStatus",
    "Confidence",
    "EvidenceReference",
    "FindingStatus",
    "ConfidenceBreakdown",
    "ConfidenceSignal",
    "SkepticReview",
    "SkepticVerdict",
    "brier_score",
    "expected_calibration_error",
    "score_confidence",
    "skeptic_review",
]
__version__ = "0.4.1"
