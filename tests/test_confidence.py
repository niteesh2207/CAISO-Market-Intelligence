from datetime import datetime, timezone

from market_intelligence.models.answer import ConfidenceLevel
from market_intelligence.models.evidence import (
    EvidenceItem,
    EvidenceKind,
    SourceTier,
)
from market_intelligence.research.confidence import calculate_confidence


def evidence(tier: SourceTier) -> EvidenceItem:
    return EvidenceItem(
        claim="Supported claim",
        kind=EvidenceKind.FACT,
        source_title="Source",
        source_url="https://example.com",
        source_tier=tier,
        retrieved_at=datetime.now(timezone.utc),
    )


def test_primary_plus_cross_check_is_high_confidence():
    result = calculate_confidence(
        [
            evidence(SourceTier.PRIMARY),
            evidence(SourceTier.REPUTABLE_SECONDARY),
        ]
    )

    assert result == ConfidenceLevel.HIGH


def test_no_evidence_is_low_confidence():
    assert calculate_confidence([]) == ConfidenceLevel.LOW


def test_conflicting_evidence_is_low_confidence():
    result = calculate_confidence(
        [evidence(SourceTier.PRIMARY)],
        has_conflict=True,
    )

    assert result == ConfidenceLevel.LOW
