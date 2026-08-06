from __future__ import annotations

from typing import Any


from market_intelligence.api.models import (
    EnergyClaimResponse,
    EnergySearchResponse,
    EnergySourceResponse,
)
from market_intelligence.service.universal_orchestrator import (
    UniversalAnswer,
)


def _enum_value(value: Any) -> str:
    return str(
        getattr(value, "value", value)
    )


def universal_answer_to_response(
    answer: UniversalAnswer,
    *,
    used_web_fallback: bool = False,
) -> EnergySearchResponse:
    route_payload = None

    if answer.route is not None:
        route_payload = {
            "domain": _enum_value(
                answer.route.domain
            ),
            "research_mode": _enum_value(
                answer.route.research_mode
            ),
            "geography": answer.route.geography,
            "entities": list(
                answer.route.matched_entities
            ),
            "providers": [
                provider.provider_id
                for provider in answer.route.providers
            ],
        }

    return EnergySearchResponse(
        status=_enum_value(answer.status),
        domain=_enum_value(answer.domain),
        answer=answer.direct_answer,
        explanation=answer.simple_explanation,
        confidence=answer.confidence,
        evidence=dict(answer.evidence_payload),
        sources=[
            EnergySourceResponse(
                provider=source.provider_id,
                title=source.title,
                url=source.url,
                primary=source.is_primary,
                role=source.source_role,
            )
            for source in answer.sources
        ],
        limitations=list(answer.limitations),
        clarification_options=list(
            answer.clarification_options
        ),
        route=route_payload,
        used_web_fallback=used_web_fallback,
    )


def cited_answer_to_response(
    answer: Any,
    *,
    domain: str,
) -> EnergySearchResponse:
    answer.validate()

    return EnergySearchResponse(
        status=str(answer.status),
        domain=domain,
        answer=answer.direct_answer,
        explanation=answer.explanation,
        confidence=answer.confidence,
        evidence=dict(
            answer.evidence_summary
        ),
        sources=[
            EnergySourceResponse(
                provider=source.provider,
                title=source.title,
                url=source.url,
                primary=(
                    source.source_tier
                    in {
                        "controlling",
                        "primary",
                    }
                ),
                role="supporting",
                source_id=source.source_id,
                source_tier=(
                    source.source_tier
                ),
                retrieved_at=(
                    source.retrieved_at
                ),
            )
            for source in answer.sources
        ],
        claims=[
            EnergyClaimResponse(
                text=claim.text,
                source_ids=list(
                    claim.source_ids
                ),
                claim_type=(
                    claim.claim_type
                ),
            )
            for claim in answer.claims
        ],
        limitations=list(
            answer.limitations
        ),
        clarification_options=[],
        route=None,
        used_web_fallback=True,
        as_of=answer.as_of,
    )
