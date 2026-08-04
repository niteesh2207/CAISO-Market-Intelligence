from __future__ import annotations

from typing import Any


from market_intelligence.api.models import (
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
