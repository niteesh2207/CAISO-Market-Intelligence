from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from market_intelligence.models.domain import (
    EnergyCommodity,
    EnergyTopic,
)
from market_intelligence.routing.energy_parser import (
    EnergyClassification,
)


class RetrievalCapability(StrEnum):
    STRUCTURED_MARKET_DATA = "structured_market_data"
    ASSET_STATUS = "asset_status"
    REGULATORY_DOCUMENTS = "regulatory_documents"
    WEATHER_DATA = "weather_data"
    COMPANY_NEWS = "company_news"
    GENERAL_WEB_RESEARCH = "general_web_research"
    HISTORICAL_ANALYSIS = "historical_analysis"


@dataclass(frozen=True)
class CapabilityPlan:
    capabilities: tuple[RetrievalCapability, ...]
    requires_exact_numeric_source: bool
    requires_current_source: bool
    requires_cross_check: bool
    minimum_sources: int


EXACT_TOPICS = {
    EnergyTopic.PRICE,
    EnergyTopic.SETTLEMENT,
    EnergyTopic.GENERATION,
    EnergyTopic.STORAGE,
    EnergyTopic.DEMAND,
    EnergyTopic.SUPPLY,
    EnergyTopic.CAPACITY,
    EnergyTopic.RESERVES,
    EnergyTopic.INVENTORY,
}


CURRENT_TOPICS = {
    EnergyTopic.ASSET_STATUS,
    EnergyTopic.OUTAGE,
    EnergyTopic.PRICE,
    EnergyTopic.SETTLEMENT,
    EnergyTopic.NEWS,
    EnergyTopic.WEATHER,
    EnergyTopic.GENERATION,
    EnergyTopic.STORAGE,
    EnergyTopic.DEMAND,
    EnergyTopic.SUPPLY,
}


def route_capabilities(
    classification: EnergyClassification,
) -> CapabilityPlan:
    capabilities: list[RetrievalCapability] = []

    if classification.topic in EXACT_TOPICS:
        capabilities.append(
            RetrievalCapability.STRUCTURED_MARKET_DATA
        )

    if classification.topic in {
        EnergyTopic.ASSET_STATUS,
        EnergyTopic.OUTAGE,
    }:
        capabilities.append(
            RetrievalCapability.ASSET_STATUS
        )

    if classification.topic in {
        EnergyTopic.REGULATORY,
        EnergyTopic.POLICY,
    }:
        capabilities.append(
            RetrievalCapability.REGULATORY_DOCUMENTS
        )

    if classification.topic == EnergyTopic.WEATHER:
        capabilities.append(
            RetrievalCapability.WEATHER_DATA
        )

    if classification.topic in {
        EnergyTopic.COMPANY,
        EnergyTopic.PROJECT,
        EnergyTopic.NEWS,
    }:
        capabilities.append(
            RetrievalCapability.COMPANY_NEWS
        )

    capabilities.append(
        RetrievalCapability.GENERAL_WEB_RESEARCH
    )

    requires_exact = (
        classification.topic in EXACT_TOPICS
    )

    requires_current = (
        classification.topic in CURRENT_TOPICS
    )

    requires_cross_check = (
        classification.topic
        in {
            EnergyTopic.PRICE,
            EnergyTopic.SETTLEMENT,
            EnergyTopic.ASSET_STATUS,
            EnergyTopic.OUTAGE,
            EnergyTopic.REGULATORY,
            EnergyTopic.NEWS,
        }
    )

    minimum_sources = 2 if requires_cross_check else 1

    return CapabilityPlan(
        capabilities=tuple(
            dict.fromkeys(capabilities)
        ),
        requires_exact_numeric_source=requires_exact,
        requires_current_source=requires_current,
        requires_cross_check=requires_cross_check,
        minimum_sources=minimum_sources,
    )
