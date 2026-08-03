from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from market_intelligence.models.domain import (
    EnergyCommodity,
    EnergyTopic,
    GeographicScope,
)
from market_intelligence.routing.capability_router import (
    CapabilityPlan,
    RetrievalCapability,
)
from market_intelligence.routing.energy_parser import (
    EnergyClassification,
)


class ProviderAccess(StrEnum):
    PUBLIC = "public"
    PUBLIC_API_KEY = "public_api_key"
    OPTIONAL_LICENSED = "optional_licensed"


class ConnectorKind(StrEnum):
    STRUCTURED_API = "structured_api"
    STRUCTURED_DOWNLOAD = "structured_download"
    DOCUMENT_SEARCH = "document_search"
    WEB_RESEARCH = "web_research"
    FILE_IMPORT = "file_import"


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    name: str
    domains: tuple[str, ...]
    commodities: tuple[EnergyCommodity, ...]
    topics: tuple[EnergyTopic, ...]
    geographies: tuple[GeographicScope, ...]
    capabilities: tuple[RetrievalCapability, ...]
    connector_kinds: tuple[ConnectorKind, ...]
    access: ProviderAccess
    authority_rank: int
    is_primary: bool
    freshness_description: str
    notes: str = ""


ALL_COMMODITIES = tuple(EnergyCommodity)
ALL_TOPICS = tuple(EnergyTopic)
ALL_GEOGRAPHIES = tuple(GeographicScope)


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        provider_id="caiso_oasis",
        name="CAISO OASIS",
        domains=(
            "oasis.caiso.com",
            "oasis-bulk.caiso.com",
        ),
        commodities=(
            EnergyCommodity.ELECTRICITY,
            EnergyCommodity.RENEWABLES,
            EnergyCommodity.STORAGE,
        ),
        topics=(
            EnergyTopic.PRICE,
            EnergyTopic.SETTLEMENT,
            EnergyTopic.CONGESTION,
            EnergyTopic.TRANSMISSION,
            EnergyTopic.GENERATION,
            EnergyTopic.DEMAND,
            EnergyTopic.SUPPLY,
            EnergyTopic.IMPORT_EXPORT,
            EnergyTopic.RESERVES,
            EnergyTopic.OUTAGE,
        ),
        geographies=(
            GeographicScope.CALIFORNIA,
            GeographicScope.WESTERN_US,
        ),
        capabilities=(
            RetrievalCapability.STRUCTURED_MARKET_DATA,
            RetrievalCapability.HISTORICAL_ANALYSIS,
        ),
        connector_kinds=(
            ConnectorKind.STRUCTURED_API,
            ConnectorKind.STRUCTURED_DOWNLOAD,
        ),
        access=ProviderAccess.PUBLIC,
        authority_rank=1,
        is_primary=True,
        freshness_description="Market and operational publication cadence",
    ),
    ProviderSpec(
        provider_id="nrc_reactor_status",
        name="U.S. Nuclear Regulatory Commission",
        domains=("nrc.gov",),
        commodities=(EnergyCommodity.NUCLEAR,),
        topics=(
            EnergyTopic.ASSET_STATUS,
            EnergyTopic.OUTAGE,
            EnergyTopic.GENERATION,
            EnergyTopic.CAPACITY,
            EnergyTopic.NEWS,
        ),
        geographies=(
            GeographicScope.UNITED_STATES,
            GeographicScope.CALIFORNIA,
            GeographicScope.TEXAS,
            GeographicScope.NORTHEAST_US,
            GeographicScope.MIDWEST_US,
            GeographicScope.SOUTHEAST_US,
        ),
        capabilities=(
            RetrievalCapability.ASSET_STATUS,
            RetrievalCapability.GENERAL_WEB_RESEARCH,
        ),
        connector_kinds=(
            ConnectorKind.STRUCTURED_DOWNLOAD,
            ConnectorKind.WEB_RESEARCH,
        ),
        access=ProviderAccess.PUBLIC,
        authority_rank=1,
        is_primary=True,
        freshness_description="Daily reactor-status reporting",
    ),
    ProviderSpec(
        provider_id="eia_api",
        name="U.S. Energy Information Administration",
        domains=("eia.gov",),
        commodities=(
            EnergyCommodity.ELECTRICITY,
            EnergyCommodity.NATURAL_GAS,
            EnergyCommodity.CRUDE_OIL,
            EnergyCommodity.REFINED_PRODUCTS,
            EnergyCommodity.COAL,
            EnergyCommodity.RENEWABLES,
            EnergyCommodity.NUCLEAR,
            EnergyCommodity.STORAGE,
            EnergyCommodity.MULTI_ENERGY,
        ),
        topics=(
            EnergyTopic.PRICE,
            EnergyTopic.GENERATION,
            EnergyTopic.FUNDAMENTALS,
            EnergyTopic.SUPPLY,
            EnergyTopic.DEMAND,
            EnergyTopic.STORAGE,
            EnergyTopic.INVENTORY,
            EnergyTopic.IMPORT_EXPORT,
            EnergyTopic.CAPACITY,
            EnergyTopic.EMISSIONS,
            EnergyTopic.NEWS,
        ),
        geographies=ALL_GEOGRAPHIES,
        capabilities=(
            RetrievalCapability.STRUCTURED_MARKET_DATA,
            RetrievalCapability.HISTORICAL_ANALYSIS,
            RetrievalCapability.GENERAL_WEB_RESEARCH,
        ),
        connector_kinds=(
            ConnectorKind.STRUCTURED_API,
            ConnectorKind.STRUCTURED_DOWNLOAD,
            ConnectorKind.WEB_RESEARCH,
        ),
        access=ProviderAccess.PUBLIC_API_KEY,
        authority_rank=2,
        is_primary=True,
        freshness_description="Dataset-specific publication cadence",
        notes="API key normally required for direct API queries",
    ),
    ProviderSpec(
        provider_id="ferc_elibrary",
        name="Federal Energy Regulatory Commission",
        domains=(
            "ferc.gov",
            "elibrary.ferc.gov",
        ),
        commodities=ALL_COMMODITIES,
        topics=(
            EnergyTopic.REGULATORY,
            EnergyTopic.POLICY,
            EnergyTopic.TRANSMISSION,
            EnergyTopic.CAPACITY,
            EnergyTopic.PROJECT,
            EnergyTopic.NEWS,
        ),
        geographies=(
            GeographicScope.UNITED_STATES,
            GeographicScope.CALIFORNIA,
            GeographicScope.TEXAS,
            GeographicScope.WESTERN_US,
            GeographicScope.NORTHEAST_US,
            GeographicScope.MIDWEST_US,
            GeographicScope.SOUTHEAST_US,
        ),
        capabilities=(
            RetrievalCapability.REGULATORY_DOCUMENTS,
            RetrievalCapability.GENERAL_WEB_RESEARCH,
        ),
        connector_kinds=(
            ConnectorKind.DOCUMENT_SEARCH,
            ConnectorKind.WEB_RESEARCH,
        ),
        access=ProviderAccess.PUBLIC,
        authority_rank=1,
        is_primary=True,
        freshness_description="Filed and issued document timestamps",
    ),
    ProviderSpec(
        provider_id="noaa_nws",
        name="NOAA and National Weather Service",
        domains=(
            "noaa.gov",
            "weather.gov",
        ),
        commodities=ALL_COMMODITIES,
        topics=(
            EnergyTopic.WEATHER,
            EnergyTopic.DEMAND,
            EnergyTopic.SUPPLY,
            EnergyTopic.GENERATION,
            EnergyTopic.NEWS,
        ),
        geographies=ALL_GEOGRAPHIES,
        capabilities=(
            RetrievalCapability.WEATHER_DATA,
            RetrievalCapability.GENERAL_WEB_RESEARCH,
        ),
        connector_kinds=(
            ConnectorKind.STRUCTURED_API,
            ConnectorKind.WEB_RESEARCH,
        ),
        access=ProviderAccess.PUBLIC,
        authority_rank=1,
        is_primary=True,
        freshness_description="Observation and forecast timestamps",
    ),
    ProviderSpec(
        provider_id="ercot",
        name="Electric Reliability Council of Texas",
        domains=("ercot.com",),
        commodities=(
            EnergyCommodity.ELECTRICITY,
            EnergyCommodity.RENEWABLES,
            EnergyCommodity.STORAGE,
        ),
        topics=(
            EnergyTopic.PRICE,
            EnergyTopic.SETTLEMENT,
            EnergyTopic.GENERATION,
            EnergyTopic.DEMAND,
            EnergyTopic.RESERVES,
            EnergyTopic.CONGESTION,
            EnergyTopic.OUTAGE,
            EnergyTopic.TRANSMISSION,
        ),
        geographies=(GeographicScope.TEXAS,),
        capabilities=(
            RetrievalCapability.STRUCTURED_MARKET_DATA,
            RetrievalCapability.ASSET_STATUS,
            RetrievalCapability.GENERAL_WEB_RESEARCH,
        ),
        connector_kinds=(
            ConnectorKind.STRUCTURED_API,
            ConnectorKind.STRUCTURED_DOWNLOAD,
            ConnectorKind.WEB_RESEARCH,
        ),
        access=ProviderAccess.PUBLIC,
        authority_rank=1,
        is_primary=True,
        freshness_description="Market and system publication cadence",
    ),
    ProviderSpec(
        provider_id="pjm",
        name="PJM Interconnection",
        domains=("pjm.com",),
        commodities=(
            EnergyCommodity.ELECTRICITY,
            EnergyCommodity.RENEWABLES,
            EnergyCommodity.STORAGE,
        ),
        topics=(
            EnergyTopic.PRICE,
            EnergyTopic.SETTLEMENT,
            EnergyTopic.GENERATION,
            EnergyTopic.DEMAND,
            EnergyTopic.CAPACITY,
            EnergyTopic.RESERVES,
            EnergyTopic.CONGESTION,
            EnergyTopic.OUTAGE,
            EnergyTopic.TRANSMISSION,
        ),
        geographies=(GeographicScope.NORTHEAST_US,),
        capabilities=(
            RetrievalCapability.STRUCTURED_MARKET_DATA,
            RetrievalCapability.ASSET_STATUS,
            RetrievalCapability.GENERAL_WEB_RESEARCH,
        ),
        connector_kinds=(
            ConnectorKind.STRUCTURED_API,
            ConnectorKind.STRUCTURED_DOWNLOAD,
            ConnectorKind.WEB_RESEARCH,
        ),
        access=ProviderAccess.PUBLIC,
        authority_rank=1,
        is_primary=True,
        freshness_description="Market and system publication cadence",
    ),
    ProviderSpec(
        provider_id="miso",
        name="Midcontinent Independent System Operator",
        domains=("misoenergy.org",),
        commodities=(
            EnergyCommodity.ELECTRICITY,
            EnergyCommodity.RENEWABLES,
            EnergyCommodity.STORAGE,
        ),
        topics=(
            EnergyTopic.PRICE,
            EnergyTopic.SETTLEMENT,
            EnergyTopic.GENERATION,
            EnergyTopic.DEMAND,
            EnergyTopic.CONGESTION,
            EnergyTopic.RESERVES,
            EnergyTopic.OUTAGE,
            EnergyTopic.TRANSMISSION,
        ),
        geographies=(GeographicScope.MIDWEST_US,),
        capabilities=(
            RetrievalCapability.STRUCTURED_MARKET_DATA,
            RetrievalCapability.GENERAL_WEB_RESEARCH,
        ),
        connector_kinds=(
            ConnectorKind.STRUCTURED_DOWNLOAD,
            ConnectorKind.WEB_RESEARCH,
        ),
        access=ProviderAccess.PUBLIC,
        authority_rank=1,
        is_primary=True,
        freshness_description="Market and system publication cadence",
    ),
    ProviderSpec(
        provider_id="spp",
        name="Southwest Power Pool",
        domains=("spp.org",),
        commodities=(
            EnergyCommodity.ELECTRICITY,
            EnergyCommodity.RENEWABLES,
            EnergyCommodity.STORAGE,
        ),
        topics=(
            EnergyTopic.PRICE,
            EnergyTopic.SETTLEMENT,
            EnergyTopic.GENERATION,
            EnergyTopic.DEMAND,
            EnergyTopic.CONGESTION,
            EnergyTopic.RESERVES,
            EnergyTopic.OUTAGE,
            EnergyTopic.TRANSMISSION,
        ),
        geographies=(GeographicScope.MIDWEST_US,),
        capabilities=(
            RetrievalCapability.STRUCTURED_MARKET_DATA,
            RetrievalCapability.GENERAL_WEB_RESEARCH,
        ),
        connector_kinds=(
            ConnectorKind.STRUCTURED_API,
            ConnectorKind.STRUCTURED_DOWNLOAD,
            ConnectorKind.WEB_RESEARCH,
        ),
        access=ProviderAccess.PUBLIC,
        authority_rank=1,
        is_primary=True,
        freshness_description="Market and system publication cadence",
    ),
    ProviderSpec(
        provider_id="reuters",
        name="Reuters",
        domains=("reuters.com",),
        commodities=ALL_COMMODITIES,
        topics=ALL_TOPICS,
        geographies=ALL_GEOGRAPHIES,
        capabilities=(
            RetrievalCapability.COMPANY_NEWS,
            RetrievalCapability.GENERAL_WEB_RESEARCH,
        ),
        connector_kinds=(ConnectorKind.WEB_RESEARCH,),
        access=ProviderAccess.PUBLIC,
        authority_rank=10,
        is_primary=False,
        freshness_description="Article publication timestamp",
    ),
    ProviderSpec(
        provider_id="woodmac_optional",
        name="Wood Mackenzie",
        domains=("woodmac.com",),
        commodities=ALL_COMMODITIES,
        topics=ALL_TOPICS,
        geographies=ALL_GEOGRAPHIES,
        capabilities=(
            RetrievalCapability.COMPANY_NEWS,
            RetrievalCapability.GENERAL_WEB_RESEARCH,
            RetrievalCapability.HISTORICAL_ANALYSIS,
        ),
        connector_kinds=(ConnectorKind.WEB_RESEARCH,),
        access=ProviderAccess.OPTIONAL_LICENSED,
        authority_rank=11,
        is_primary=False,
        freshness_description="Publication or licensed-dataset timestamp",
        notes="Licensed content requires authorized access",
    ),
)


def provider_by_id(
    provider_id: str,
) -> ProviderSpec | None:
    for provider in PROVIDERS:
        if provider.provider_id == provider_id:
            return provider

    return None


def provider_by_domain(
    domain: str,
) -> ProviderSpec | None:
    normalized = (
        domain.lower()
        .strip()
        .removeprefix("https://")
        .removeprefix("http://")
        .removeprefix("www.")
        .split("/", 1)[0]
    )

    matches = [
        provider
        for provider in PROVIDERS
        if any(
            normalized == candidate
            or normalized.endswith(f".{candidate}")
            for candidate in provider.domains
        )
    ]

    if not matches:
        return None

    return sorted(
        matches,
        key=lambda item: (
            item.authority_rank,
            item.name,
        ),
    )[0]


def matching_providers(
    classification: EnergyClassification,
    capability_plan: CapabilityPlan,
    *,
    include_licensed: bool = False,
) -> list[ProviderSpec]:
    required_capabilities = set(
        capability_plan.capabilities
    )

    matches: list[ProviderSpec] = []

    for provider in PROVIDERS:
        if (
            provider.access
            == ProviderAccess.OPTIONAL_LICENSED
            and not include_licensed
        ):
            continue

        commodity_match = (
            classification.commodity
            in provider.commodities
            or EnergyCommodity.UNKNOWN
            == classification.commodity
        )

        topic_match = (
            classification.topic
            in provider.topics
            or classification.topic
            == EnergyTopic.GENERAL
        )

        geography_match = (
            classification.geography
            in provider.geographies
            or classification.geography
            == GeographicScope.UNKNOWN
            or GeographicScope.GLOBAL
            in provider.geographies
        )

        capability_match = bool(
            required_capabilities.intersection(
                provider.capabilities
            )
        )

        if (
            commodity_match
            and topic_match
            and geography_match
            and capability_match
        ):
            matches.append(provider)

    return sorted(
        matches,
        key=lambda item: (
            item.authority_rank,
            not item.is_primary,
            item.name,
        ),
    )
