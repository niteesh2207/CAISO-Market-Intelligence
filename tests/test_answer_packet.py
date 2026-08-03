from datetime import datetime, timezone

import pytest

from market_intelligence.answers.composer import (
    compose_answer_packet,
)
from market_intelligence.answers.models import (
    AnswerClaim,
    AnswerSource,
    ConfidenceLevel,
)
from market_intelligence.answers.validation import (
    AnswerValidationError,
    validate_answer_packet,
)
from market_intelligence.quality.models import (
    ClaimType,
    QualityAssessment,
    ReleaseDecision,
)


NOW = datetime.now(timezone.utc)


def source(
    *,
    source_id: str = "primary-1",
    is_primary: bool = True,
) -> AnswerSource:
    return AnswerSource(
        source_id=source_id,
        provider_id="test-provider",
        title="Official source",
        url="https://example.com/source",
        is_primary=is_primary,
        authority_rank=1,
        observed_at=NOW,
        published_at=NOW,
        retrieved_at=NOW,
    )


def quality(
    *,
    decision=ReleaseDecision.RELEASE,
    score=100,
    warnings=(),
) -> QualityAssessment:
    return QualityAssessment(
        decision=decision,
        score=score,
        issues=(),
        warnings=warnings,
        rationale="Test assessment",
    )


def test_valid_numeric_answer_packet():
    packet = compose_answer_packet(
        question="What did the market settle at?",
        direct_answer="The price settled at $45/MWh.",
        simple_explanation=(
            "The official market record shows a "
            "settlement price of $45/MWh."
        ),
        claims=[
            AnswerClaim(
                claim_id="settlement-price",
                text="Settlement price was $45/MWh.",
                claim_type=ClaimType.NUMERIC_FACT,
                source_ids=("primary-1",),
                value=45.0,
                unit="USD/MWh",
                market="Day-ahead market",
                timezone="America/Los_Angeles",
                interval="hourly",
            )
        ],
        sources=[source()],
        quality_assessment=quality(),
    )

    assert packet.confidence == ConfidenceLevel.HIGH
    assert packet.primary_source_count == 1


def test_numeric_claim_without_unit_is_rejected():
    with pytest.raises(
        AnswerValidationError,
        match="missing a unit",
    ):
        compose_answer_packet(
            question="What was the price?",
            direct_answer="The price was 45.",
            simple_explanation="Official result.",
            claims=[
                AnswerClaim(
                    claim_id="bad-price",
                    text="Price was 45.",
                    claim_type=ClaimType.NUMERIC_FACT,
                    source_ids=("primary-1",),
                    value=45,
                    market="Day-ahead",
                    timezone="UTC",
                )
            ],
            sources=[source()],
            quality_assessment=quality(),
        )


def test_unknown_source_reference_is_rejected():
    with pytest.raises(
        AnswerValidationError,
        match="unknown sources",
    ):
        compose_answer_packet(
            question="Is the unit operating?",
            direct_answer="The unit is operating.",
            simple_explanation="The status is reported online.",
            claims=[
                AnswerClaim(
                    claim_id="status",
                    text="Unit is operating.",
                    claim_type=ClaimType.OBSERVED_FACT,
                    source_ids=("missing-source",),
                )
            ],
            sources=[source()],
            quality_assessment=quality(),
        )


def test_blocked_answer_requires_limitation():
    with pytest.raises(
        AnswerValidationError,
        match="must explain why",
    ):
        compose_answer_packet(
            question="What was the exact price?",
            direct_answer=(
                "The exact price cannot be confirmed."
            ),
            simple_explanation=(
                "Available evidence is incomplete."
            ),
            claims=[],
            sources=[],
            quality_assessment=quality(
                decision=(
                    ReleaseDecision.REFUSE_NUMERIC_CLAIM
                ),
                score=20,
            ),
        )


def test_secondary_only_answer_gets_warning():
    packet = compose_answer_packet(
        question="What happened?",
        direct_answer="A market event occurred.",
        simple_explanation="Reporting indicates an event.",
        claims=[
            AnswerClaim(
                claim_id="event",
                text="A market event occurred.",
                claim_type=ClaimType.OBSERVED_FACT,
                source_ids=("secondary-1",),
            )
        ],
        sources=[
            source(
                source_id="secondary-1",
                is_primary=False,
            )
        ],
        quality_assessment=quality(
            decision=ReleaseDecision.RELEASE_WITH_WARNING,
            score=65,
            warnings=(
                "No controlling primary source was available.",
            ),
        ),
    )

    result = validate_answer_packet(packet)

    assert result.valid is True
    assert (
        "The answer contains no primary source."
        in result.warnings
    )
    assert packet.confidence == ConfidenceLevel.LOW


def test_medium_quality_maps_to_medium_confidence():
    packet = compose_answer_packet(
        question="What changed?",
        direct_answer="Conditions changed.",
        simple_explanation="Two sources report the change.",
        claims=[
            AnswerClaim(
                claim_id="change",
                text="Conditions changed.",
                claim_type=ClaimType.EXPLANATION,
                source_ids=("primary-1",),
            )
        ],
        sources=[source()],
        quality_assessment=quality(
            decision=ReleaseDecision.RELEASE_WITH_WARNING,
            score=78,
            warnings=("Freshness should be disclosed.",),
        ),
    )

    assert packet.confidence == ConfidenceLevel.MEDIUM
