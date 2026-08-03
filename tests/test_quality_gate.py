from datetime import (
    datetime,
    timedelta,
    timezone,
)

from market_intelligence.quality.gate import (
    assess_evidence_quality,
)
from market_intelligence.quality.models import (
    ClaimRequirement,
    ClaimType,
    EvidenceQualityInput,
    QualityIssue,
    ReleaseDecision,
)


NOW = datetime(
    2026,
    8,
    3,
    15,
    0,
    tzinfo=timezone.utc,
)


def quality_input(**overrides):
    values = {
        "record_count": 2,
        "primary_record_count": 1,
        "independent_source_count": 2,
        "newest_observed_at": NOW - timedelta(minutes=15),
        "oldest_observed_at": NOW - timedelta(minutes=30),
        "evaluated_at": NOW,
        "has_source_conflict": False,
        "complete_coverage": True,
        "has_unit": True,
        "has_market_context": True,
        "has_timezone": True,
        "calculation_verified": True,
    }

    values.update(overrides)

    return EvidenceQualityInput(**values)


def test_complete_numeric_evidence_is_released():
    result = assess_evidence_quality(
        quality_input(),
        claim_type=ClaimType.NUMERIC_FACT,
    )

    assert result.decision == ReleaseDecision.RELEASE
    assert result.score == 100
    assert result.issues == ()


def test_numeric_claim_without_unit_is_refused():
    result = assess_evidence_quality(
        quality_input(has_unit=False),
        claim_type=ClaimType.NUMERIC_FACT,
    )

    assert (
        result.decision
        == ReleaseDecision.REFUSE_NUMERIC_CLAIM
    )
    assert QualityIssue.MISSING_UNIT in result.issues


def test_numeric_claim_without_observation_time_is_refused():
    result = assess_evidence_quality(
        quality_input(newest_observed_at=None),
        claim_type=ClaimType.NUMERIC_FACT,
    )

    assert (
        result.decision
        == ReleaseDecision.REFUSE_NUMERIC_CLAIM
    )
    assert (
        QualityIssue.MISSING_OBSERVATION_TIME
        in result.issues
    )


def test_source_conflict_holds_answer():
    result = assess_evidence_quality(
        quality_input(has_source_conflict=True),
        claim_type=ClaimType.EXPLANATION,
    )

    assert result.decision == ReleaseDecision.HOLD
    assert QualityIssue.SOURCE_CONFLICT in result.issues


def test_secondary_only_explanation_releases_with_warning():
    result = assess_evidence_quality(
        quality_input(
            primary_record_count=0,
        ),
        claim_type=ClaimType.EXPLANATION,
    )

    assert (
        result.decision
        == ReleaseDecision.RELEASE_WITH_WARNING
    )
    assert (
        QualityIssue.NO_PRIMARY_SOURCE
        in result.issues
    )


def test_unverified_calculation_is_refused():
    result = assess_evidence_quality(
        quality_input(
            calculation_verified=False,
        ),
        claim_type=ClaimType.CALCULATION,
    )

    assert (
        result.decision
        == ReleaseDecision.REFUSE_NUMERIC_CLAIM
    )
    assert (
        QualityIssue.UNVERIFIED_CALCULATION
        in result.issues
    )


def test_stale_evidence_is_disclosed():
    requirement = ClaimRequirement(
        claim_type=ClaimType.OBSERVED_FACT,
        requires_primary_source=True,
        maximum_age_seconds=3600,
    )

    result = assess_evidence_quality(
        quality_input(
            newest_observed_at=NOW - timedelta(hours=3),
        ),
        claim_type=ClaimType.OBSERVED_FACT,
        requirement=requirement,
    )

    assert (
        result.decision
        == ReleaseDecision.RELEASE_WITH_WARNING
    )
    assert QualityIssue.STALE_EVIDENCE in result.issues


def test_no_evidence_is_held():
    result = assess_evidence_quality(
        quality_input(
            record_count=0,
            primary_record_count=0,
            independent_source_count=0,
            newest_observed_at=None,
        ),
        claim_type=ClaimType.OBSERVED_FACT,
    )

    assert result.decision == ReleaseDecision.HOLD
    assert QualityIssue.NO_EVIDENCE in result.issues
