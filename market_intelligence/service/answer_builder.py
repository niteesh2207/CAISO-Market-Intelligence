from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from market_intelligence.answers.models import (
    AnswerClaim,
)
from market_intelligence.quality.models import (
    ClaimType,
)
from market_intelligence.retrieval.models import (
    RetrievedRecord,
)
from market_intelligence.routing.energy_parser import (
    EnergyClassification,
)


@dataclass(frozen=True)
class AnswerDraft:
    direct_answer: str
    simple_explanation: str
    claims: tuple[AnswerClaim, ...]
    limitations: tuple[str, ...] = ()


AnswerDraftBuilder = Callable[
    [
        str,
        EnergyClassification,
        tuple[RetrievedRecord, ...],
        ClaimType,
        dict[str, Any],
    ],
    AnswerDraft,
]


def default_answer_draft_builder(
    question: str,
    classification: EnergyClassification,
    records: tuple[RetrievedRecord, ...],
    claim_type: ClaimType,
    context: dict[str, Any],
) -> AnswerDraft:
    if not records:
        return AnswerDraft(
            direct_answer=(
                "The requested information could not be "
                "verified from accessible authoritative sources."
            ),
            simple_explanation=(
                "The research process did not obtain enough "
                "usable evidence to confirm the answer."
            ),
            claims=(),
            limitations=(
                "No usable evidence record was retrieved.",
            ),
        )

    first = records[0]
    payload = first.payload

    if isinstance(payload, dict):
        answer_text = (
            payload.get("direct_answer")
            or payload.get("summary")
            or payload.get("answer")
        )
        explanation = (
            payload.get("simple_explanation")
            or payload.get("explanation")
        )
    else:
        answer_text = None
        explanation = None

    direct_answer = str(
        answer_text
        or "Authoritative evidence was retrieved successfully."
    )

    simple_explanation = str(
        explanation
        or (
            "The answer is based on the highest-ranked "
            "accessible evidence returned by the research pipeline."
        )
    )

    claim = AnswerClaim(
        claim_id="claim-1",
        text=direct_answer,
        claim_type=claim_type,
        source_ids=tuple(
            f"source-{index + 1}"
            for index, _ in enumerate(records)
        ),
        value=(
            payload.get("value")
            if isinstance(payload, dict)
            else None
        ),
        unit=(
            payload.get("unit")
            if isinstance(payload, dict)
            else None
        ),
        market=(
            payload.get("market")
            if isinstance(payload, dict)
            else None
        ),
        timezone=(
            payload.get("timezone")
            if isinstance(payload, dict)
            else None
        ),
        interval=(
            payload.get("interval")
            if isinstance(payload, dict)
            else None
        ),
        is_inference=(
            claim_type
            in {
                ClaimType.ANALYST_INFERENCE,
                ClaimType.EXPLANATION,
                ClaimType.FORECAST,
            }
        ),
    )

    return AnswerDraft(
        direct_answer=direct_answer,
        simple_explanation=simple_explanation,
        claims=(claim,),
    )
