from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from market_intelligence.models.query import Market, QueryIntent


class AccessType(StrEnum):
    PUBLIC = "public"
    LICENSED_OPTIONAL = "licensed_optional"


@dataclass(frozen=True)
class SourceAuthority:
    source_id: str
    name: str
    domains: tuple[str, ...]
    markets: tuple[Market, ...]
    intents: tuple[QueryIntent, ...]
    authority_rank: int
    is_primary: bool
    access_type: AccessType = AccessType.PUBLIC


SOURCE_AUTHORITIES: tuple[SourceAuthority, ...] = (
    SourceAuthority(
        source_id="caiso_oasis",
        name="CAISO OASIS",
        domains=(
            "oasis.caiso.com",
            "oasis-bulk.caiso.com",
        ),
        markets=(Market.CAISO,),
        intents=(
            QueryIntent.PRICE,
            QueryIntent.CONGESTION,
            QueryIntent.FUNDAMENTALS,
            QueryIntent.OUTAGE,
        ),
        authority_rank=1,
        is_primary=True,
    ),
    SourceAuthority(
        source_id="caiso",
        name="California ISO",
        domains=("caiso.com",),
        markets=(Market.CAISO, Market.WEST),
        intents=(
            QueryIntent.PRICE,
            QueryIntent.GENERATION,
            QueryIntent.OUTAGE,
            QueryIntent.CONGESTION,
            QueryIntent.FUNDAMENTALS,
            QueryIntent.NEWS,
        ),
        authority_rank=2,
        is_primary=True,
    ),
    SourceAuthority(
        source_id="nrc",
        name="U.S. Nuclear Regulatory Commission",
        domains=("nrc.gov",),
        markets=(
            Market.CAISO,
            Market.WEST,
            Market.GENERAL,
        ),
        intents=(
            QueryIntent.GENERATION,
            QueryIntent.OUTAGE,
            QueryIntent.NEWS,
        ),
        authority_rank=1,
        is_primary=True,
    ),
    SourceAuthority(
        source_id="eia",
        name="U.S. Energy Information Administration",
        domains=("eia.gov",),
        markets=tuple(Market),
        intents=(
            QueryIntent.GENERATION,
            QueryIntent.FUNDAMENTALS,
            QueryIntent.GAS,
            QueryIntent.NEWS,
        ),
        authority_rank=2,
        is_primary=True,
    ),
    SourceAuthority(
        source_id="ferc",
        name="Federal Energy Regulatory Commission",
        domains=("ferc.gov",),
        markets=tuple(Market),
        intents=(
            QueryIntent.REGULATORY,
            QueryIntent.NEWS,
            QueryIntent.CONGESTION,
        ),
        authority_rank=1,
        is_primary=True,
    ),
    SourceAuthority(
        source_id="noaa_nws",
        name="NOAA and National Weather Service",
        domains=(
            "noaa.gov",
            "weather.gov",
        ),
        markets=tuple(Market),
        intents=(
            QueryIntent.WEATHER,
            QueryIntent.FUNDAMENTALS,
            QueryIntent.NEWS,
        ),
        authority_rank=1,
        is_primary=True,
    ),
    SourceAuthority(
        source_id="cpuc",
        name="California Public Utilities Commission",
        domains=("cpuc.ca.gov",),
        markets=(Market.CAISO, Market.WEST),
        intents=(
            QueryIntent.REGULATORY,
            QueryIntent.GAS,
            QueryIntent.NEWS,
        ),
        authority_rank=2,
        is_primary=True,
    ),
    SourceAuthority(
        source_id="cec",
        name="California Energy Commission",
        domains=("energy.ca.gov",),
        markets=(Market.CAISO, Market.WEST),
        intents=(
            QueryIntent.GENERATION,
            QueryIntent.FUNDAMENTALS,
            QueryIntent.REGULATORY,
            QueryIntent.NEWS,
        ),
        authority_rank=2,
        is_primary=True,
    ),
    SourceAuthority(
        source_id="bpa",
        name="Bonneville Power Administration",
        domains=("bpa.gov",),
        markets=(Market.WEST,),
        intents=(
            QueryIntent.GENERATION,
            QueryIntent.FUNDAMENTALS,
            QueryIntent.OUTAGE,
            QueryIntent.NEWS,
        ),
        authority_rank=2,
        is_primary=True,
    ),
    SourceAuthority(
        source_id="reuters",
        name="Reuters",
        domains=("reuters.com",),
        markets=tuple(Market),
        intents=tuple(QueryIntent),
        authority_rank=10,
        is_primary=False,
    ),
    SourceAuthority(
        source_id="wood_mackenzie_public",
        name="Wood Mackenzie Public Research",
        domains=("woodmac.com",),
        markets=tuple(Market),
        intents=tuple(QueryIntent),
        authority_rank=11,
        is_primary=False,
        access_type=AccessType.LICENSED_OPTIONAL,
    ),
    SourceAuthority(
        source_id="sp_global_public",
        name="S&P Global Public Content",
        domains=("spglobal.com",),
        markets=tuple(Market),
        intents=tuple(QueryIntent),
        authority_rank=11,
        is_primary=False,
        access_type=AccessType.LICENSED_OPTIONAL,
    ),
)


def matching_sources(
    *,
    market: Market,
    intent: QueryIntent,
    include_licensed: bool = False,
) -> list[SourceAuthority]:
    matches = [
        source
        for source in SOURCE_AUTHORITIES
        if (
            market in source.markets
            and intent in source.intents
            and (
                include_licensed
                or source.access_type
                != AccessType.LICENSED_OPTIONAL
            )
        )
    ]

    return sorted(
        matches,
        key=lambda source: (
            source.authority_rank,
            source.name,
        ),
    )


def source_by_domain(
    domain: str,
) -> SourceAuthority | None:
    normalized = domain.lower().removeprefix("www.")

    for source in SOURCE_AUTHORITIES:
        if any(
            normalized == candidate
            or normalized.endswith(f".{candidate}")
            for candidate in source.domains
        ):
            return source

    return None
