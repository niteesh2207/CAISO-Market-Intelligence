from __future__ import annotations

# Public web-search authorities only. Licensed publishers are deliberately
# excluded: premium data must arrive through an entitled server-side connector,
# not public-page scraping or search snippets.

COMMON_AUTHORITIES = [
    "caiso.com",
    "oasis.caiso.com",
    "oasis-bulk.caiso.com",
    "ferc.gov",
    "data.ferc.gov",
    "eia.gov",
    "energy.ca.gov",
    "cpuc.ca.gov",
    "noaa.gov",
    "weather.gov",
    "bpa.gov",
    "nrc.gov",
    "pge.com",
    "sce.com",
    "sdge.com",
    "socalgas.com",
    "pacificorp.com",
    "ladwp.com",
    "smud.org",
    "reuters.com",
]

INTENT_DOMAINS = {
    "price": [
        "caiso.com", "oasis.caiso.com", "oasis-bulk.caiso.com",
        "ferc.gov", "data.ferc.gov", "reuters.com",
    ],
    "generation": [
        "caiso.com", "nrc.gov", "pge.com", "sce.com", "sdge.com",
        "reuters.com",
    ],
    "grid": [
        "caiso.com", "bpa.gov", "ferc.gov", "pge.com", "sce.com", "sdge.com",
        "pacificorp.com",
    ],
    "west": [
        "caiso.com", "bpa.gov", "pacificorp.com", "ferc.gov", "eia.gov",
        "reuters.com",
    ],
    "gas": [
        "socalgas.com", "pge.com", "eia.gov", "caiso.com", "ferc.gov",
        "reuters.com",
    ],
    "weather": [
        "noaa.gov", "weather.gov", "caiso.com", "bpa.gov",
    ],
    "regulatory": [
        "ferc.gov", "cpuc.ca.gov", "energy.ca.gov", "caiso.com", "eia.gov",
    ],
    "general": COMMON_AUTHORITIES,
}


def classify_intent(question: str) -> str:
    q = question.lower()

    if any(x in q for x in (
        "np15", "np-15", "sp15", "sp-15",
        "lmp", "price", "settle", "settlement",
        "day-ahead", "day ahead",
        "real-time", "real time",
    )):
        return "price"

    if any(x in q for x in (
        "diablo", "generator", "unit ",
        "ramp down", "ramp up", "offline",
        "derate", "nuclear", "plant output",
    )):
        return "generation"

    # Evaluate gas before grid. Otherwise "pipeline"
    # can be incorrectly captured by a generic "line" rule.
    if any(x in q for x in (
        "socalgas", "so cal gas",
        "pg&e citygate", "pge citygate",
        "natural gas", "gas price",
        "henry hub", "citygate",
        "pipeline", "freeport lng",
        "lng", "ofo", "storage gas",
    )):
        return "gas"

    if any(x in q for x in (
        "constraint", "congestion",
        "transmission", "outage",
        "transmission line", "power line",
        "line outage", "transformer",
        "path 26", "path 15", "flowgate",
    )):
        return "grid"

    if any(x in q for x in (
        "bpa", "pacw", "pace",
        "mid-c", "mid c", "malin",
        "palo verde", "northwest",
        "pnw", "western", "edam transfer",
    )):
        return "west"

    if any(x in q for x in (
        "weather", "temperature", "heat",
        "cloud", "irradiance", "wind forecast",
    )):
        return "weather"

    if any(x in q for x in (
        "ferc", "cpuc", "cec",
        "tariff", "filing",
        "regulatory", "rule",
    )):
        return "regulatory"

    return "general"


def domains_for_intent(intent: str) -> list[str]:
    # Responses web_search supports up to 100 allowed domains.
    domains = INTENT_DOMAINS.get(intent, COMMON_AUTHORITIES)
    return list(dict.fromkeys(domains))
