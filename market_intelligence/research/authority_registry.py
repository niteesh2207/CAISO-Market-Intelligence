from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class AuthorityRecord:
    domain: str
    tier: str
    organization: str
    categories: tuple[str, ...]


AUTHORITY_RECORDS = (
    AuthorityRecord(
        domain="eia.gov",
        tier="controlling",
        organization=(
            "U.S. Energy Information Administration"
        ),
        categories=(
            "electricity",
            "natural_gas",
            "petroleum",
            "generation",
            "demand",
        ),
    ),
    AuthorityRecord(
        domain="ferc.gov",
        tier="controlling",
        organization=(
            "Federal Energy Regulatory Commission"
        ),
        categories=(
            "regulation",
            "transmission",
            "natural_gas",
            "lng",
        ),
    ),
    AuthorityRecord(
        domain="energy.gov",
        tier="controlling",
        organization=(
            "U.S. Department of Energy"
        ),
        categories=(
            "electricity",
            "generation",
            "infrastructure",
        ),
    ),
    AuthorityRecord(
        domain="nrc.gov",
        tier="controlling",
        organization=(
            "U.S. Nuclear Regulatory Commission"
        ),
        categories=(
            "nuclear",
            "reactor_status",
        ),
    ),
    AuthorityRecord(
        domain="noaa.gov",
        tier="controlling",
        organization=(
            "National Oceanic and "
            "Atmospheric Administration"
        ),
        categories=(
            "weather",
            "climate",
        ),
    ),
    AuthorityRecord(
        domain="weather.gov",
        tier="controlling",
        organization=(
            "National Weather Service"
        ),
        categories=(
            "weather",
        ),
    ),
    AuthorityRecord(
        domain="caiso.com",
        tier="controlling",
        organization=(
            "California Independent "
            "System Operator"
        ),
        categories=(
            "electricity",
            "market",
            "transmission",
            "generation",
        ),
    ),
    AuthorityRecord(
        domain="ercot.com",
        tier="controlling",
        organization=(
            "Electric Reliability "
            "Council of Texas"
        ),
        categories=(
            "electricity",
            "market",
            "transmission",
        ),
    ),
    AuthorityRecord(
        domain="pjm.com",
        tier="controlling",
        organization="PJM Interconnection",
        categories=(
            "electricity",
            "market",
            "transmission",
        ),
    ),
    AuthorityRecord(
        domain="misoenergy.org",
        tier="controlling",
        organization="MISO",
        categories=(
            "electricity",
            "market",
            "transmission",
        ),
    ),
    AuthorityRecord(
        domain="spp.org",
        tier="controlling",
        organization="Southwest Power Pool",
        categories=(
            "electricity",
            "market",
            "transmission",
        ),
    ),
    AuthorityRecord(
        domain="nyiso.com",
        tier="controlling",
        organization=(
            "New York Independent "
            "System Operator"
        ),
        categories=(
            "electricity",
            "market",
            "transmission",
        ),
    ),
    AuthorityRecord(
        domain="iso-ne.com",
        tier="controlling",
        organization="ISO New England",
        categories=(
            "electricity",
            "market",
            "transmission",
        ),
    ),
    AuthorityRecord(
        domain="nerc.com",
        tier="controlling",
        organization=(
            "North American Electric "
            "Reliability Corporation"
        ),
        categories=(
            "reliability",
            "transmission",
        ),
    ),
    AuthorityRecord(
        domain="energy.ca.gov",
        tier="controlling",
        organization=(
            "California Energy Commission"
        ),
        categories=(
            "electricity",
            "infrastructure",
            "generation",
            "demand",
        ),
    ),
    AuthorityRecord(
        domain="cpuc.ca.gov",
        tier="controlling",
        organization=(
            "California Public "
            "Utilities Commission"
        ),
        categories=(
            "regulation",
            "utility",
            "infrastructure",
        ),
    ),
    AuthorityRecord(
        domain="sdge.com",
        tier="primary",
        organization="San Diego Gas & Electric",
        categories=(
            "utility",
            "electricity",
            "infrastructure",
            "service_territory",
        ),
    ),
    AuthorityRecord(
        domain="sec.gov",
        tier="controlling",
        organization=(
            "U.S. Securities and "
            "Exchange Commission"
        ),
        categories=(
            "company",
            "financial",
            "asset",
        ),
    ),
)


def normalize_domain(
    value: str,
) -> str:
    cleaned = value.strip().lower()

    if "://" in cleaned:
        cleaned = (
            urlsplit(cleaned).hostname
            or ""
        )

    return cleaned.removeprefix("www.")


def domain_matches(
    hostname: str,
    target: str,
) -> bool:
    hostname = normalize_domain(hostname)
    target = normalize_domain(target)

    return (
        hostname == target
        or hostname.endswith(
            "." + target
        )
    )


def authority_for_url(
    url: str,
) -> AuthorityRecord | None:
    hostname = normalize_domain(url)

    if "://" in url:
        hostname = normalize_domain(
            urlsplit(url).hostname or ""
        )

    for record in AUTHORITY_RECORDS:
        if domain_matches(
            hostname,
            record.domain,
        ):
            return record

    return None
