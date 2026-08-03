from __future__ import annotations

from datetime import datetime, timezone

from market_intelligence.answers.models import (
    AnswerClaim,
    AnswerPacket,
    AnswerSource,
    ConfidenceLevel,
)
from market_intelligence.answers.validation import (
    require_valid_answer,
)
from market_intelligence.quality.models import (
    QualityAssessment,
    ReleaseDecision,
)


def confidence_from_quality(
    assessment: QualityAssessment,
) -> ConfidenceLevel:
    if assessment.decision in {
        ReleaseDecision.HOLD,
        ReleaseDecision.REFUSE_NUMERIC_CLAIM,
    }:
        return ConfidenceLevel.INSUFFICIENT

    if assessment.score >= 90:
        return ConfidenceLevel.HIGH

    if assessment.score >= 70:
        return ConfidenceLevel.MEDIUM

    return ConfidenceLevel.LOW


def compose_answer_packet(
    *,
    question: str,
    direct_answer: str,
    simple_explanation: str,
    claims: list[AnswerClaim],
    sources: list[AnswerSource],
    quality_assessment: QualityAssessment,
    additional_limitations: list[str] | None = None,
) -> AnswerPacket:
    limitations = list(
        quality_assessment.warnings
    )

    if additional_limitations:
        limitations.extend(
            additional_limitations
        )

    packet = AnswerPacket(
        question=question.strip(),
        direct_answer=direct_answer.strip(),
        simple_explanation=simple_explanation.strip(),
        claims=tuple(claims),
        sources=tuple(sources),
        confidence=confidence_from_quality(
            quality_assessment
        ),
        release_decision=quality_assessment.decision,
        limitations=tuple(
            dict.fromkeys(limitations)
        ),
        generated_at=datetime.now(timezone.utc),
    )

    require_valid_answer(packet)

    return packet
