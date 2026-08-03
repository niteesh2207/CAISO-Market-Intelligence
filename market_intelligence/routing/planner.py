from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from market_intelligence.models.query import (
    MarketQuery,
    QueryIntent,
)
from market_intelligence.research.source_policy import (
    matching_sources,
)


class ResearchMode(StrEnum):
    STRUCTURED_FIRST = "structured_first"
    WEB_FIRST = "web_first"
    HYBRID = "hybrid"


class ResearchPlan(BaseModel):
    mode: ResearchMode
    requires_structured_data: bool
    requires_web_research: bool
    minimum_primary_sources: int = Field(ge=0)
    minimum_total_sources: int = Field(ge=0)
    preferred_source_ids: list[str] = Field(
        default_factory=list
    )
    required_connectors: list[str] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(
        default_factory=list
    )


STRUCTURED_FIRST_INTENTS = {
    QueryIntent.PRICE,
    QueryIntent.GENERATION,
    QueryIntent.OUTAGE,
    QueryIntent.CONGESTION,
    QueryIntent.FUNDAMENTALS,
    QueryIntent.WEATHER,
}


def build_research_plan(
    query: MarketQuery,
) -> ResearchPlan:
    requires_structured = (
        query.intent in STRUCTURED_FIRST_INTENTS
    )

    requires_web = query.intent in {
        QueryIntent.NEWS,
        QueryIntent.REGULATORY,
        QueryIntent.GAS,
        QueryIntent.OUTAGE,
        QueryIntent.GENERATION,
        QueryIntent.CONGESTION,
        QueryIntent.FUNDAMENTALS,
        QueryIntent.WEATHER,
        QueryIntent.GENERAL,
    }

    if requires_structured and requires_web:
        mode = ResearchMode.HYBRID
    elif requires_structured:
        mode = ResearchMode.STRUCTURED_FIRST
    else:
        mode = ResearchMode.WEB_FIRST

    sources = matching_sources(
        market=query.market,
        intent=query.intent,
    )

    required_connectors: list[str] = []
    warnings: list[str] = []

    if (
        query.market.value == "CAISO"
        and query.intent == QueryIntent.PRICE
    ):
        required_connectors.append("caiso_oasis")

        if not query.nodes:
            warnings.append(
                "The requested CAISO price location is ambiguous."
            )

        if query.requested_date is None:
            warnings.append(
                "The requested CAISO market date is ambiguous."
            )

    if (
        query.intent
        in {
            QueryIntent.GENERATION,
            QueryIntent.OUTAGE,
        }
        and any(
            "diablo canyon" in asset.lower()
            for asset in query.assets
        )
    ):
        required_connectors.append("nrc_reactor_status")

    if (
        "diablo canyon"
        in query.raw_question.lower()
        and "nrc_reactor_status"
        not in required_connectors
    ):
        required_connectors.append("nrc_reactor_status")

    primary_requirement = (
        1
        if query.intent != QueryIntent.GENERAL
        else 0
    )

    total_requirement = (
        2
        if requires_web
        else 1
    )

    return ResearchPlan(
        mode=mode,
        requires_structured_data=requires_structured,
        requires_web_research=requires_web,
        minimum_primary_sources=primary_requirement,
        minimum_total_sources=total_requirement,
        preferred_source_ids=[
            source.source_id
            for source in sources
        ],
        required_connectors=required_connectors,
        warnings=warnings,
    )
