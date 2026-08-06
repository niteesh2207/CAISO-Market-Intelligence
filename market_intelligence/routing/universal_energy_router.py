from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re


class EnergyDomain(StrEnum):
    ELECTRICITY_MARKETS = "electricity_markets"
    GRID_RELIABILITY = "grid_reliability"
    NUCLEAR = "nuclear"
    NATURAL_GAS = "natural_gas"
    PETROLEUM = "petroleum"
    COAL = "coal"
    RENEWABLES = "renewables"
    ENERGY_STORAGE = "energy_storage"
    WEATHER = "weather"
    TRANSMISSION_REGULATION = "transmission_regulation"
    COMPANY_ASSET = "company_asset"
    EMISSIONS_CARBON = "emissions_carbon"
    GENERAL_ENERGY = "general_energy"
    UNKNOWN = "unknown"


class ResearchMode(StrEnum):
    STRUCTURED_DATA = "structured_data"
    OFFICIAL_DOCUMENT = "official_document"
    CURRENT_NEWS = "current_news"
    HYBRID_RESEARCH = "hybrid_research"
    CLARIFICATION = "clarification"


class FreshnessNeed(StrEnum):
    LIVE = "live"
    CURRENT = "current"
    HISTORICAL = "historical"
    STABLE = "stable"


@dataclass(frozen=True)
class ProviderPlan:
    provider_id: str
    priority: int
    source_role: str
    retrieval_modes: tuple[str, ...]


@dataclass(frozen=True)
class UniversalEnergyRoute:
    question: str
    domain: EnergyDomain
    research_mode: ResearchMode
    freshness: FreshnessNeed
    providers: tuple[ProviderPlan, ...]
    matched_entities: tuple[str, ...]
    geography: str | None
    requires_cross_source_validation: bool
    clarification: str | None = None


LARGE_LOAD_TERMS = (
    "data center",
    "data centers",
    "data centre",
    "data centres",
    "large load",
    "hyperscale",
    "hyperscaler",
    "ai load",
    "industrial load",
    "campus load",
    "load growth",
    "interconnection project",
)


DOMAIN_KEYWORDS: dict[EnergyDomain, tuple[str, ...]] = {
    EnergyDomain.NUCLEAR: (
        "nuclear",
        "reactor",
        "diablo canyon",
        "palo verde",
        "nrc",
        "refueling outage",
        "unit power",
    ),
    EnergyDomain.NATURAL_GAS: (
        "natural gas",
        "henry hub",
        "gas storage",
        "pipeline",
        "lng",
        "bcf",
        "mmbtu",
        "gas production",
        "gas price",
    ),
    EnergyDomain.PETROLEUM: (
        "crude oil",
        "brent",
        "wti",
        "petroleum",
        "gasoline",
        "diesel",
        "refinery",
        "oil inventory",
        "opec",
    ),
    EnergyDomain.COAL: (
        "coal",
        "coal generation",
        "coal production",
        "coal stockpile",
    ),
    EnergyDomain.ENERGY_STORAGE: (
        "battery",
        "bess",
        "energy storage",
        "storage capacity",
        "battery charging",
        "battery discharge",
    ),
    EnergyDomain.RENEWABLES: (
        "solar",
        "wind",
        "renewable",
        "curtailment",
        "hydro",
        "geothermal",
        "renewable generation",
    ),
    EnergyDomain.WEATHER: (
        "weather",
        "temperature",
        "heat",
        "heat wave",
        "extreme heat",
        "cold",
        "cold snap",
        "hurricane",
        "storm",
        "wind forecast",
        "solar irradiance",
        "degree days",
    ),
    EnergyDomain.TRANSMISSION_REGULATION: (
        "ferc",
        "nerc",
        "transmission planning",
        "tariff",
        "order 1920",
        "rulemaking",
        "rate case",
        "interconnection queue",
        "reliability standard",
    ),
    EnergyDomain.GRID_RELIABILITY: (
        "reserve margin",
        "operating reserve",
        "grid emergency",
        "energy emergency",
        "load shed",
        "reliability",
        "outage",
        "forced outage",
        "transmission constraint",
    ),
    EnergyDomain.EMISSIONS_CARBON: (
        "carbon",
        "co2",
        "emissions",
        "allowance price",
        "cap and trade",
        "rggi",
    ),
    EnergyDomain.COMPANY_ASSET: (
        "earnings",
        "company",
        "acquisition",
        "merger",
        "project status",
        "commercial operation",
        "construction",
        "investor",
        "asset sale",
    ),
    EnergyDomain.ELECTRICITY_MARKETS: (
        *LARGE_LOAD_TERMS,
        "lmp",
        "electricity price",
        "power price",
        "day ahead",
        "real time",
        "fifteen minute",
        "settlement",
        "np15",
        "np 15",
        "sp15",
        "sp 15",
        "ercot",
        "caiso",
        "pjm",
        "miso",
        "spp",
        "nyiso",
        "iso ne",
        "congestion",
        "load",
        "generation mix",
    ),
}


DOMAIN_PRIORITY = (
    EnergyDomain.NUCLEAR,
    EnergyDomain.NATURAL_GAS,
    EnergyDomain.PETROLEUM,
    EnergyDomain.COAL,
    EnergyDomain.ENERGY_STORAGE,
    EnergyDomain.RENEWABLES,
    EnergyDomain.WEATHER,
    EnergyDomain.TRANSMISSION_REGULATION,
    EnergyDomain.GRID_RELIABILITY,
    EnergyDomain.EMISSIONS_CARBON,
    EnergyDomain.COMPANY_ASSET,
    EnergyDomain.ELECTRICITY_MARKETS,
)


PROVIDER_PLANS: dict[
    EnergyDomain,
    tuple[ProviderPlan, ...],
] = {
    EnergyDomain.ELECTRICITY_MARKETS: (
        ProviderPlan(
            "iso_rto_structured_data",
            1,
            "controlling",
            ("api", "bulk_download"),
        ),
        ProviderPlan(
            "eia_api",
            2,
            "corroborating",
            ("api",),
        ),
        ProviderPlan(
            "reliable_energy_news",
            3,
            "context",
            ("news_search",),
        ),
    ),
    EnergyDomain.GRID_RELIABILITY: (
        ProviderPlan(
            "iso_rto_operational_data",
            1,
            "controlling",
            ("api", "official_web"),
        ),
        ProviderPlan(
            "nerc",
            2,
            "controlling",
            ("official_document", "official_web"),
        ),
        ProviderPlan(
            "noaa_nws",
            3,
            "causal_context",
            ("api", "official_web"),
        ),
    ),
    EnergyDomain.NUCLEAR: (
        ProviderPlan(
            "nrc_reactor_status",
            1,
            "controlling",
            ("official_web", "structured_report"),
        ),
        ProviderPlan(
            "nrc_documents",
            2,
            "controlling",
            ("official_document",),
        ),
        ProviderPlan(
            "operator_primary_source",
            3,
            "corroborating",
            ("official_web", "company_release"),
        ),
    ),
    EnergyDomain.NATURAL_GAS: (
        ProviderPlan(
            "eia_api",
            1,
            "controlling",
            ("api",),
        ),
        ProviderPlan(
            "ferc_elibrary",
            2,
            "regulatory",
            ("official_document",),
        ),
        ProviderPlan(
            "pipeline_primary_source",
            3,
            "operational",
            ("official_web",),
        ),
        ProviderPlan(
            "reliable_energy_news",
            4,
            "context",
            ("news_search",),
        ),
    ),
    EnergyDomain.PETROLEUM: (
        ProviderPlan(
            "eia_api",
            1,
            "controlling",
            ("api",),
        ),
        ProviderPlan(
            "government_statistics",
            2,
            "corroborating",
            ("api", "official_document"),
        ),
        ProviderPlan(
            "reliable_energy_news",
            3,
            "context",
            ("news_search",),
        ),
    ),
    EnergyDomain.COAL: (
        ProviderPlan(
            "eia_api",
            1,
            "controlling",
            ("api",),
        ),
        ProviderPlan(
            "government_statistics",
            2,
            "corroborating",
            ("official_document",),
        ),
    ),
    EnergyDomain.RENEWABLES: (
        ProviderPlan(
            "iso_rto_structured_data",
            1,
            "operational",
            ("api", "bulk_download"),
        ),
        ProviderPlan(
            "eia_api",
            2,
            "controlling",
            ("api",),
        ),
        ProviderPlan(
            "noaa_nws",
            3,
            "weather_context",
            ("api",),
        ),
        ProviderPlan(
            "operator_primary_source",
            4,
            "asset_context",
            ("official_web",),
        ),
    ),
    EnergyDomain.ENERGY_STORAGE: (
        ProviderPlan(
            "iso_rto_structured_data",
            1,
            "operational",
            ("api", "bulk_download"),
        ),
        ProviderPlan(
            "eia_api",
            2,
            "capacity",
            ("api",),
        ),
        ProviderPlan(
            "operator_primary_source",
            3,
            "asset_context",
            ("official_web",),
        ),
    ),
    EnergyDomain.WEATHER: (
        ProviderPlan(
            "noaa_nws",
            1,
            "controlling",
            ("api", "official_web"),
        ),
        ProviderPlan(
            "iso_rto_operational_data",
            2,
            "market_impact",
            ("api",),
        ),
    ),
    EnergyDomain.TRANSMISSION_REGULATION: (
        ProviderPlan(
            "ferc_elibrary",
            1,
            "controlling",
            ("official_document",),
        ),
        ProviderPlan(
            "iso_rto_documents",
            2,
            "implementation",
            ("official_document", "official_web"),
        ),
        ProviderPlan(
            "nerc",
            3,
            "reliability",
            ("official_document",),
        ),
        ProviderPlan(
            "reliable_energy_news",
            4,
            "context",
            ("news_search",),
        ),
    ),
    EnergyDomain.COMPANY_ASSET: (
        ProviderPlan(
            "company_primary_source",
            1,
            "controlling",
            ("company_release", "investor_relations"),
        ),
        ProviderPlan(
            "sec_filings",
            2,
            "controlling",
            ("official_document",),
        ),
        ProviderPlan(
            "regulator_primary_source",
            3,
            "corroborating",
            ("official_document",),
        ),
        ProviderPlan(
            "reliable_energy_news",
            4,
            "context",
            ("news_search",),
        ),
    ),
    EnergyDomain.EMISSIONS_CARBON: (
        ProviderPlan(
            "government_environment_data",
            1,
            "controlling",
            ("api", "official_document"),
        ),
        ProviderPlan(
            "market_operator_data",
            2,
            "market_data",
            ("api",),
        ),
        ProviderPlan(
            "reliable_energy_news",
            3,
            "context",
            ("news_search",),
        ),
    ),
}


GEOGRAPHY_PATTERNS = {
    "california": (
        "california",
        "caiso",
        "sdg&e",
        "sdge",
        "san diego gas and electric",
        "np15",
        "np 15",
        "sp15",
        "sp 15",
    ),
    "texas": (
        "texas",
        "ercot",
    ),
    "pjm": (
        "pjm",
    ),
    "midcontinent": (
        "miso",
        "midcontinent",
    ),
    "southwest_power_pool": (
        "spp",
        "southwest power pool",
    ),
    "new_york": (
        "nyiso",
        "new york",
    ),
    "new_england": (
        "iso ne",
        "iso-ne",
        "new england",
    ),
    "united_states": (
        "united states",
        "u s ",
        "us energy",
        "national",
    ),
}


ENTITY_PATTERNS = (
    "diablo canyon",
    "henry hub",
    "brent",
    "wti",
    "np-15",
    "sp-15",
    "zp-26",
    "caiso",
    "ercot",
    "pjm",
    "miso",
    "spp",
    "nyiso",
    "iso-ne",
    "ferc",
    "nerc",
    "nrc",
    "eia",
)


ENTITY_ALIASES: dict[str, tuple[str, ...]] = {
    "sdg&e": (
        "sdg&e",
        "sdge",
        "sdg and e",
        "san diego gas and electric",
    ),
}


def _normalize(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        value.lower(),
    ).strip()


def _contains_term(
    normalized_question: str,
    term: str,
) -> bool:
    normalized_term = _normalize(term)

    return bool(
        normalized_term
        and re.search(
            rf"\b{re.escape(normalized_term)}\b",
            normalized_question,
        )
    )


def _classify_domain(
    question: str,
) -> EnergyDomain:
    normalized = _normalize(question)
    scores: dict[EnergyDomain, int] = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(
            1
            for keyword in keywords
            if _contains_term(normalized, keyword)
        )

        if score:
            scores[domain] = score

    if not scores:
        if any(
            term in normalized
            for term in (
                "energy",
                "power",
                "fuel",
                "generation",
            )
        ):
            return EnergyDomain.GENERAL_ENERGY

        return EnergyDomain.UNKNOWN

    best_score = max(scores.values())

    for domain in DOMAIN_PRIORITY:
        if scores.get(domain) == best_score:
            return domain

    return max(scores, key=scores.get)


def _resolve_geography(
    question: str,
) -> str | None:
    normalized = _normalize(question)

    for geography, terms in GEOGRAPHY_PATTERNS.items():
        if any(
            _contains_term(normalized, term)
            for term in terms
        ):
            return geography

    return None


def _extract_entities(
    question: str,
) -> tuple[str, ...]:
    normalized = _normalize(question)
    entities = []

    for entity in ENTITY_PATTERNS:
        if _contains_term(normalized, entity):
            entities.append(entity)

    for canonical, aliases in ENTITY_ALIASES.items():
        if any(
            _contains_term(normalized, alias)
            for alias in aliases
        ):
            entities.append(canonical)

    return tuple(entities)


def _resolve_freshness(
    question: str,
) -> FreshnessNeed:
    normalized = _normalize(question)

    if any(
        term in normalized
        for term in (
            "right now",
            "currently",
            "today",
            "live",
            "this hour",
            "latest status",
        )
    ):
        return FreshnessNeed.LIVE

    if any(
        term in normalized
        for term in (
            "latest",
            "recent",
            "yesterday",
            "this week",
            "this month",
            "new ",
            "news",
        )
    ):
        return FreshnessNeed.CURRENT

    if re.search(
        r"\b(19|20)\d{2}\b",
        normalized,
    ):
        return FreshnessNeed.HISTORICAL

    return FreshnessNeed.STABLE


def _resolve_research_mode(
    question: str,
    domain: EnergyDomain,
) -> ResearchMode:
    normalized = _normalize(question)

    if domain == EnergyDomain.UNKNOWN:
        return ResearchMode.CLARIFICATION

    # Regulatory and company/asset questions must begin
    # with controlling primary documents. Current news and
    # explanatory context can be added later by the research
    # orchestrator without displacing the primary-source route.
    if domain in {
        EnergyDomain.TRANSMISSION_REGULATION,
        EnergyDomain.COMPANY_ASSET,
    }:
        return ResearchMode.OFFICIAL_DOCUMENT

    if any(
        term in normalized
        for term in (
            "news",
            "latest development",
            "what happened",
            "why did",
            "why does",
            "why do",
            "why is",
            "why are",
            "why was",
            "why were",
            "what caused",
            "what is causing",
            "reason for",
            "outlook",
            "impact",
            "affect",
            "effect",
        )
    ):
        return ResearchMode.HYBRID_RESEARCH

    if domain in {
        EnergyDomain.ELECTRICITY_MARKETS,
        EnergyDomain.GRID_RELIABILITY,
        EnergyDomain.NUCLEAR,
        EnergyDomain.NATURAL_GAS,
        EnergyDomain.PETROLEUM,
        EnergyDomain.COAL,
        EnergyDomain.RENEWABLES,
        EnergyDomain.ENERGY_STORAGE,
        EnergyDomain.WEATHER,
        EnergyDomain.EMISSIONS_CARBON,
    }:
        return ResearchMode.STRUCTURED_DATA

    return ResearchMode.HYBRID_RESEARCH


def route_energy_question(
    question: str,
) -> UniversalEnergyRoute:
    cleaned = question.strip()

    if not cleaned:
        raise ValueError(
            "Energy question cannot be empty."
        )

    domain = _classify_domain(cleaned)
    mode = _resolve_research_mode(
        cleaned,
        domain,
    )
    freshness = _resolve_freshness(cleaned)
    geography = _resolve_geography(cleaned)
    entities = _extract_entities(cleaned)

    if domain == EnergyDomain.UNKNOWN:
        return UniversalEnergyRoute(
            question=cleaned,
            domain=domain,
            research_mode=ResearchMode.CLARIFICATION,
            freshness=freshness,
            providers=(),
            matched_entities=entities,
            geography=geography,
            requires_cross_source_validation=False,
            clarification=(
                "Please provide an energy-market, fuel, "
                "asset, regulatory or grid-related question."
            ),
        )

    providers = PROVIDER_PLANS.get(
        domain,
        (
            ProviderPlan(
                "universal_energy_research",
                1,
                "discovery",
                ("official_web", "news_search"),
            ),
        ),
    )

    cross_source = (
        mode == ResearchMode.HYBRID_RESEARCH
        or domain in {
            EnergyDomain.GRID_RELIABILITY,
            EnergyDomain.TRANSMISSION_REGULATION,
            EnergyDomain.COMPANY_ASSET,
        }
    )

    return UniversalEnergyRoute(
        question=cleaned,
        domain=domain,
        research_mode=mode,
        freshness=freshness,
        providers=providers,
        matched_entities=entities,
        geography=geography,
        requires_cross_source_validation=cross_source,
    )
