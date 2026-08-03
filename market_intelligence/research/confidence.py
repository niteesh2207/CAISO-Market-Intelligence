from __future__ import annotations

from market_intelligence.models.answer import ConfidenceLevel
from market_intelligence.models.evidence import (
    EvidenceItem,
    SourceTier,
)


def calculate_confidence(
    evidence: list[EvidenceItem],
    *,
    has_conflict: bool = False,
    incomplete_intervals: bool = False,
) -> ConfidenceLevel:
    if not evidence:
        return ConfidenceLevel.LOW

    primary_count = sum(
        item.source_tier == SourceTier.PRIMARY
        for item in evidence
    )

    if has_conflict or incomplete_intervals:
        return ConfidenceLevel.LOW

    if primary_count >= 1 and len(evidence) >= 2:
        return ConfidenceLevel.HIGH

    if primary_count >= 1:
        return ConfidenceLevel.MEDIUM

    return ConfidenceLevel.LOW
