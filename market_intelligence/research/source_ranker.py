from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlparse

from market_intelligence.research.models import (
    SearchResult,
    SourceTier,
)


CONTROLLING_DOMAINS = {
    "caiso.com",
    "ercot.com",
    "pjm.com",
    "misoenergy.org",
    "spp.org",
    "nyiso.com",
    "iso-ne.com",
    "eia.gov",
    "ferc.gov",
    "nrc.gov",
    "noaa.gov",
    "weather.gov",
    "nerc.com",
    "energy.gov",
    "epa.gov",
    "ca.gov",
}

AUTHORITATIVE_DOMAINS = {
    "reuters.com",
    "sec.gov",
    "nasdaq.com",
    "nyse.com",
}

ENERGY_TERMS = {
    "energy",
    "electricity",
    "power",
    "grid",
    "generator",
    "generation",
    "hydro",
    "solar",
    "wind",
    "natural gas",
    "oil",
    "lng",
    "transmission",
    "curtailment",
    "outage",
    "capacity",
    "demand",
    "load",
    "price",
}


def normalized_domain(url: str) -> str:
    hostname = (urlparse(url).hostname or "").lower()

    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname


def domain_matches(domain: str, approved: set[str]) -> bool:
    return any(
        domain == candidate
        or domain.endswith("." + candidate)
        for candidate in approved
    )


def classify_source(url: str) -> SourceTier:
    domain = normalized_domain(url)

    if domain_matches(domain, CONTROLLING_DOMAINS):
        return SourceTier.CONTROLLING

    if domain_matches(domain, AUTHORITATIVE_DOMAINS):
        return SourceTier.AUTHORITATIVE

    if domain:
        return SourceTier.SUPPORTING

    return SourceTier.UNKNOWN


def relevance_score(
    result: SearchResult,
    question: str,
) -> float:
    combined = " ".join(
        (
            result.title,
            result.snippet,
            result.domain,
        )
    ).lower()

    question_terms = {
        term.strip(".,?!:;()[]{}").lower()
        for term in question.split()
        if len(term.strip(".,?!:;()[]{}")) >= 3
    }

    overlap = sum(
        1
        for term in question_terms
        if term in combined
    )

    energy_overlap = sum(
        1
        for term in ENERGY_TERMS
        if term in combined
    )

    tier = classify_source(result.url)

    tier_bonus = {
        SourceTier.CONTROLLING: 50.0,
        SourceTier.AUTHORITATIVE: 30.0,
        SourceTier.SUPPORTING: 10.0,
        SourceTier.UNKNOWN: 0.0,
    }[tier]

    return (
        tier_bonus
        + overlap * 4.0
        + energy_overlap * 1.5
    )


def rank_results(
    results: list[SearchResult],
    question: str,
) -> list[SearchResult]:
    ranked: list[SearchResult] = []

    for result in results:
        domain = result.domain or normalized_domain(
            result.url
        )

        tier = classify_source(result.url)

        scored = replace(
            result,
            domain=domain,
            source_tier=tier,
            score=relevance_score(
                replace(result, domain=domain),
                question,
            ),
        )

        ranked.append(scored)

    return sorted(
        ranked,
        key=lambda item: item.score,
        reverse=True,
    )
