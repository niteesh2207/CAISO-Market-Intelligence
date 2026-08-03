from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ClaimType(StrEnum):
    OBSERVED_FACT = "observed_fact"
    NUMERIC_FACT = "numeric_fact"
    CALCULATION = "calculation"
    EXPLANATION = "explanation"
    ANALYST_INFERENCE = "analyst_inference"
    FORECAST = "forecast"


class ReleaseDecision(StrEnum):
    RELEASE = "release"
    RELEASE_WITH_WARNING = "release_with_warning"
    HOLD = "hold"
    REFUSE_NUMERIC_CLAIM = "refuse_numeric_claim"


class QualityIssue(StrEnum):
    NO_EVIDENCE = "no_evidence"
    NO_PRIMARY_SOURCE = "no_primary_source"
    STALE_EVIDENCE = "stale_evidence"
    MISSING_OBSERVATION_TIME = "missing_observation_time"
    SOURCE_CONFLICT = "source_conflict"
    INCOMPLETE_COVERAGE = "incomplete_coverage"
    MISSING_UNIT = "missing_unit"
    MISSING_MARKET_CONTEXT = "missing_market_context"
    MISSING_TIMEZONE = "missing_timezone"
    UNVERIFIED_CALCULATION = "unverified_calculation"
    INSUFFICIENT_CROSS_CHECK = "insufficient_cross_check"


@dataclass(frozen=True)
class ClaimRequirement:
    claim_type: ClaimType
    requires_primary_source: bool = True
    requires_cross_check: bool = False
    requires_observation_time: bool = False
    requires_unit: bool = False
    requires_market_context: bool = False
    requires_timezone: bool = False
    maximum_age_seconds: int | None = None
    minimum_records: int = 1


@dataclass(frozen=True)
class EvidenceQualityInput:
    record_count: int
    primary_record_count: int
    independent_source_count: int
    newest_observed_at: datetime | None
    oldest_observed_at: datetime | None
    evaluated_at: datetime
    has_source_conflict: bool = False
    complete_coverage: bool = True
    has_unit: bool = True
    has_market_context: bool = True
    has_timezone: bool = True
    calculation_verified: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QualityAssessment:
    decision: ReleaseDecision
    score: int
    issues: tuple[QualityIssue, ...]
    warnings: tuple[str, ...]
    rationale: str

    @property
    def releasable(self) -> bool:
        return self.decision in {
            ReleaseDecision.RELEASE,
            ReleaseDecision.RELEASE_WITH_WARNING,
        }
