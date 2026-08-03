from __future__ import annotations

from dataclasses import dataclass

from market_intelligence.answers.models import (
    AnswerPacket,
)
from market_intelligence.quality.models import (
    ClaimType,
    ReleaseDecision,
)


class AnswerValidationError(ValueError):
    """Raised when an answer packet is unsafe to publish."""


@dataclass(frozen=True)
class AnswerValidationResult:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def validate_answer_packet(
    packet: AnswerPacket,
) -> AnswerValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    source_ids = {
        source.source_id
        for source in packet.sources
    }

    if not packet.question.strip():
        errors.append("Question cannot be empty.")

    if not packet.direct_answer.strip():
        errors.append("Direct answer cannot be empty.")

    if not packet.simple_explanation.strip():
        errors.append(
            "Simple explanation cannot be empty."
        )

    if packet.release_decision in {
        ReleaseDecision.HOLD,
        ReleaseDecision.REFUSE_NUMERIC_CLAIM,
    }:
        if not packet.limitations:
            errors.append(
                "A blocked or refused answer must explain why."
            )

    for claim in packet.claims:
        missing_sources = [
            source_id
            for source_id in claim.source_ids
            if source_id not in source_ids
        ]

        if missing_sources:
            errors.append(
                f"Claim {claim.claim_id!r} references unknown "
                f"sources: {missing_sources}."
            )

        if (
            claim.claim_type
            in {
                ClaimType.NUMERIC_FACT,
                ClaimType.CALCULATION,
            }
            and claim.value is not None
        ):
            if not claim.unit:
                errors.append(
                    f"Numeric claim {claim.claim_id!r} "
                    "is missing a unit."
                )

            if not claim.market:
                errors.append(
                    f"Numeric claim {claim.claim_id!r} "
                    "is missing market context."
                )

            if not claim.timezone:
                errors.append(
                    f"Numeric claim {claim.claim_id!r} "
                    "is missing timezone context."
                )

        if claim.is_inference and not claim.source_ids:
            errors.append(
                f"Inference {claim.claim_id!r} has no "
                "supporting evidence."
            )

    if packet.primary_source_count == 0:
        warnings.append(
            "The answer contains no primary source."
        )

    if packet.source_count < 2:
        warnings.append(
            "The answer has fewer than two sources."
        )

    return AnswerValidationResult(
        valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def require_valid_answer(
    packet: AnswerPacket,
) -> None:
    result = validate_answer_packet(packet)

    if not result.valid:
        raise AnswerValidationError(
            " | ".join(result.errors)
        )
