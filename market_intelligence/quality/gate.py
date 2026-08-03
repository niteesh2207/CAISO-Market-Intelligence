from __future__ import annotations

from datetime import timezone

from market_intelligence.quality.models import (
    ClaimRequirement,
    ClaimType,
    EvidenceQualityInput,
    QualityAssessment,
    QualityIssue,
    ReleaseDecision,
)
from market_intelligence.quality.policies import (
    requirement_for,
)


def _age_seconds(
    quality_input: EvidenceQualityInput,
) -> float | None:
    observed_at = quality_input.newest_observed_at

    if observed_at is None:
        return None

    evaluated_at = quality_input.evaluated_at

    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(
            tzinfo=timezone.utc
        )

    if evaluated_at.tzinfo is None:
        evaluated_at = evaluated_at.replace(
            tzinfo=timezone.utc
        )

    return max(
        0.0,
        (
            evaluated_at.astimezone(timezone.utc)
            - observed_at.astimezone(timezone.utc)
        ).total_seconds(),
    )


def assess_evidence_quality(
    quality_input: EvidenceQualityInput,
    *,
    claim_type: ClaimType,
    requirement: ClaimRequirement | None = None,
) -> QualityAssessment:
    requirement = (
        requirement
        or requirement_for(claim_type)
    )

    issues: list[QualityIssue] = []
    warnings: list[str] = []
    score = 100

    if quality_input.record_count == 0:
        issues.append(QualityIssue.NO_EVIDENCE)
        score -= 100

    if (
        quality_input.record_count
        < requirement.minimum_records
    ):
        issues.append(
            QualityIssue.INSUFFICIENT_CROSS_CHECK
        )
        score -= 25

    if (
        requirement.requires_primary_source
        and quality_input.primary_record_count == 0
    ):
        issues.append(
            QualityIssue.NO_PRIMARY_SOURCE
        )
        score -= 35

    if (
        requirement.requires_cross_check
        and quality_input.independent_source_count < 2
    ):
        if (
            QualityIssue.INSUFFICIENT_CROSS_CHECK
            not in issues
        ):
            issues.append(
                QualityIssue.INSUFFICIENT_CROSS_CHECK
            )

        score -= 20

    if (
        requirement.requires_observation_time
        and quality_input.newest_observed_at is None
    ):
        issues.append(
            QualityIssue.MISSING_OBSERVATION_TIME
        )
        score -= 20

    maximum_age = requirement.maximum_age_seconds

    if maximum_age is not None:
        age_seconds = _age_seconds(quality_input)

        if (
            age_seconds is not None
            and age_seconds > maximum_age
        ):
            issues.append(
                QualityIssue.STALE_EVIDENCE
            )
            score -= 25

    if quality_input.has_source_conflict:
        issues.append(
            QualityIssue.SOURCE_CONFLICT
        )
        score -= 35

    if not quality_input.complete_coverage:
        issues.append(
            QualityIssue.INCOMPLETE_COVERAGE
        )
        score -= 20

    if (
        requirement.requires_unit
        and not quality_input.has_unit
    ):
        issues.append(
            QualityIssue.MISSING_UNIT
        )
        score -= 20

    if (
        requirement.requires_market_context
        and not quality_input.has_market_context
    ):
        issues.append(
            QualityIssue.MISSING_MARKET_CONTEXT
        )
        score -= 20

    if (
        requirement.requires_timezone
        and not quality_input.has_timezone
    ):
        issues.append(
            QualityIssue.MISSING_TIMEZONE
        )
        score -= 15

    if (
        claim_type == ClaimType.CALCULATION
        and not quality_input.calculation_verified
    ):
        issues.append(
            QualityIssue.UNVERIFIED_CALCULATION
        )
        score -= 35

    score = max(0, min(100, score))

    numeric_blocking_issues = {
        QualityIssue.NO_EVIDENCE,
        QualityIssue.MISSING_UNIT,
        QualityIssue.MISSING_MARKET_CONTEXT,
        QualityIssue.MISSING_OBSERVATION_TIME,
        QualityIssue.UNVERIFIED_CALCULATION,
    }

    hard_hold_issues = {
        QualityIssue.NO_EVIDENCE,
        QualityIssue.SOURCE_CONFLICT,
    }

    if (
        claim_type
        in {
            ClaimType.NUMERIC_FACT,
            ClaimType.CALCULATION,
        }
        and numeric_blocking_issues.intersection(
            issues
        )
    ):
        decision = ReleaseDecision.REFUSE_NUMERIC_CLAIM

    elif hard_hold_issues.intersection(issues):
        decision = ReleaseDecision.HOLD

    elif score >= 85 and not issues:
        decision = ReleaseDecision.RELEASE

    elif score >= 55:
        decision = ReleaseDecision.RELEASE_WITH_WARNING

    else:
        decision = ReleaseDecision.HOLD

    for issue in issues:
        if issue == QualityIssue.NO_PRIMARY_SOURCE:
            warnings.append(
                "No controlling primary source was available."
            )
        elif issue == QualityIssue.STALE_EVIDENCE:
            warnings.append(
                "The newest available observation is older than "
                "the permitted freshness threshold."
            )
        elif issue == QualityIssue.INCOMPLETE_COVERAGE:
            warnings.append(
                "The retrieved dataset does not cover every "
                "required interval or record."
            )
        elif issue == QualityIssue.SOURCE_CONFLICT:
            warnings.append(
                "Material sources disagree and the conflict "
                "has not been resolved."
            )
        elif issue == QualityIssue.MISSING_UNIT:
            warnings.append(
                "The numerical value does not have a verified unit."
            )
        elif issue == QualityIssue.MISSING_TIMEZONE:
            warnings.append(
                "The applicable timezone was not verified."
            )
        elif issue == QualityIssue.INSUFFICIENT_CROSS_CHECK:
            warnings.append(
                "The claim does not have the required independent "
                "source confirmation."
            )

    if decision == ReleaseDecision.RELEASE:
        rationale = (
            "Evidence meets all configured release requirements."
        )
    elif decision == ReleaseDecision.RELEASE_WITH_WARNING:
        rationale = (
            "The evidence is usable, but the answer must disclose "
            "the identified limitations."
        )
    elif decision == ReleaseDecision.REFUSE_NUMERIC_CLAIM:
        rationale = (
            "The exact numerical claim cannot be released because "
            "one or more mandatory numerical controls are missing."
        )
    else:
        rationale = (
            "The evidence is not strong enough to publish the claim "
            "as confirmed."
        )

    return QualityAssessment(
        decision=decision,
        score=score,
        issues=tuple(dict.fromkeys(issues)),
        warnings=tuple(dict.fromkeys(warnings)),
        rationale=rationale,
    )
