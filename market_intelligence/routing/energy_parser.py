from __future__ import annotations

from dataclasses import dataclass
import re

from market_intelligence.models.domain import (
    EnergyCommodity,
    EnergyTopic,
    GeographicScope,
)


@dataclass(frozen=True)
class EnergyClassification:
    commodity: EnergyCommodity
    topic: EnergyTopic
    geography: GeographicScope
    entities: tuple[str, ...]
    keywords: tuple[str, ...]


COMMODITY_PATTERNS: tuple[
    tuple[EnergyCommodity, tuple[str, ...]],
    ...
] = (
    (
        EnergyCommodity.STORAGE,
        (
            "battery",
            "bess",
            "energy storage",
            "state of charge",
            "charging",
            "discharging",
        ),
    ),
    (
        EnergyCommodity.NUCLEAR,
        (
            "nuclear",
            "reactor",
            "diablo canyon",
        ),
    ),
    (
        EnergyCommodity.NATURAL_GAS,
        (
            "natural gas",
            "henry hub",
            "citygate",
            "pipeline",
            "lng",
            "gas storage",
            "bcf",
            "mmbtu",
            "freeport lng",
        ),
    ),
    (
        EnergyCommodity.CRUDE_OIL,
        (
            "brent",
            "wti",
            "crude oil",
            "crude",
            "oil price",
            "opec",
            "barrel",
        ),
    ),
    (
        EnergyCommodity.REFINED_PRODUCTS,
        (
            "gasoline",
            "diesel",
            "jet fuel",
            "heating oil",
            "refinery",
            "crack spread",
        ),
    ),
    (
        EnergyCommodity.COAL,
        (
            "thermal coal",
            "met coal",
            "coal",
        ),
    ),
    (
        EnergyCommodity.RENEWABLES,
        (
            "solar",
            "wind generation",
            "hydro",
            "renewable",
            "curtailment",
        ),
    ),
    (
        EnergyCommodity.CARBON,
        (
            "carbon",
            "emissions allowance",
            "cap-and-trade",
            "rggi",
            "cca price",
        ),
    ),
    (
        EnergyCommodity.HYDROGEN,
        (
            "green hydrogen",
            "blue hydrogen",
            "hydrogen",
        ),
    ),
    (
        EnergyCommodity.ELECTRICITY,
        (
            "electricity",
            "power price",
            "np-15",
            "np15",
            "sp-15",
            "sp15",
            "lmp",
            "day-ahead",
            "day ahead",
            "real-time",
            "real time",
            "megawatt",
            "mwh",
            "transmission",
            "congestion",
            "load",
            "grid",
            "ercot",
            "caiso",
            "pjm",
            "miso",
            "spp",
            "nyiso",
            "iso-ne",
        ),
    ),
)


TOPIC_PATTERNS: tuple[
    tuple[EnergyTopic, tuple[str, ...]],
    ...
] = (
    (
        EnergyTopic.SETTLEMENT,
        (
            "settle",
            "settlement",
            "cleared at",
        ),
    ),
    (
        EnergyTopic.ASSET_STATUS,
        (
            "running",
            "operating",
            "online",
            "offline",
            "full capacity",
            "derated",
            "status",
        ),
    ),
    (
        EnergyTopic.OUTAGE,
        (
            "forced outage",
            "planned outage",
            "outage",
            "trip",
        ),
    ),
    (
        EnergyTopic.CONGESTION,
        (
            "binding constraint",
            "shadow price",
            "congestion",
            "flowgate",
        ),
    ),
    (
        EnergyTopic.TRANSMISSION,
        (
            "transfer capability",
            "transmission",
            "line rating",
            "intertie",
        ),
    ),
    (
        EnergyTopic.GENERATION,
        (
            "capacity factor",
            "generation",
            "output",
            "producing",
        ),
    ),
    (
        EnergyTopic.STORAGE,
        (
            "storage level",
            "inventory",
            "injection",
            "withdrawal",
            "state of charge",
        ),
    ),
    (
        EnergyTopic.DEMAND,
        (
            "load forecast",
            "consumption",
            "demand",
        ),
    ),
    (
        EnergyTopic.SUPPLY,
        (
            "availability",
            "production",
            "supply",
        ),
    ),
    (
        EnergyTopic.IMPORT_EXPORT,
        (
            "interchange",
            "imports",
            "exports",
            "flows",
        ),
    ),
    (
        EnergyTopic.CAPACITY,
        (
            "capacity market",
            "installed capacity",
            "nameplate capacity",
            "battery capacity",
        ),
    ),
    (
        EnergyTopic.RESERVES,
        (
            "reserve margin",
            "operating reserves",
            "ancillary services",
        ),
    ),
    (
        EnergyTopic.WEATHER,
        (
            "weather",
            "temperature",
            "heat wave",
            "cold snap",
            "wind forecast",
        ),
    ),
    (
        EnergyTopic.REGULATORY,
        (
            "commission order",
            "regulatory",
            "ferc",
            "tariff",
            "filing",
        ),
    ),
    (
        EnergyTopic.POLICY,
        (
            "legislation",
            "tax credit",
            "subsidy",
            "policy",
        ),
    ),
    (
        EnergyTopic.COMPANY,
        (
            "acquisition",
            "earnings",
            "company",
            "merger",
        ),
    ),
    (
        EnergyTopic.PROJECT,
        (
            "commercial operation",
            "construction",
            "project",
            "permit",
        ),
    ),
    (
        EnergyTopic.EMISSIONS,
        (
            "carbon intensity",
            "emissions",
            "co2",
        ),
    ),
    (
        EnergyTopic.NEWS,
        (
            "what happened",
            "latest",
            "update",
            "news",
        ),
    ),
    (
        EnergyTopic.PRICE,
        (
            "price",
            "lmp",
            "cost",
            "spread",
            "basis",
        ),
    ),
)


GEOGRAPHY_PATTERNS: tuple[
    tuple[GeographicScope, tuple[str, ...]],
    ...
] = (
    (
        GeographicScope.CALIFORNIA,
        (
            "diablo canyon",
            "california",
            "caiso",
            "np-15",
            "np15",
            "sp-15",
            "sp15",
        ),
    ),
    (
        GeographicScope.TEXAS,
        (
            "houston hub",
            "north hub",
            "texas",
            "ercot",
        ),
    ),
    (
        GeographicScope.WESTERN_US,
        (
            "western interconnection",
            "western us",
            "palo verde",
            "mid-c",
            "bpa",
        ),
    ),
    (
        GeographicScope.NORTHEAST_US,
        (
            "new england",
            "new york",
            "iso-ne",
            "nyiso",
            "pjm",
        ),
    ),
    (
        GeographicScope.MIDWEST_US,
        (
            "midwest",
            "miso",
            "spp",
        ),
    ),
    (
        GeographicScope.EUROPE,
        (
            "european",
            "europe",
            "germany",
            "france",
            "ttf",
        ),
    ),
    (
        GeographicScope.CANADA,
        (
            "alberta",
            "ontario",
            "canada",
            "aeso",
            "ieso",
        ),
    ),
    (
        GeographicScope.GLOBAL,
        (
            "worldwide",
            "international",
            "global",
            "opec",
        ),
    ),
)


ENTITY_PATTERNS = (
    r"\bNP-?15\b",
    r"\bSP-?15\b",
    r"\bHenry Hub\b",
    r"\bBrent\b",
    r"\bWTI\b",
    r"\bDiablo Canyon\b",
    r"\bFreeport LNG\b",
    r"\bERCOT\b",
    r"\bCAISO\b",
    r"\bPJM\b",
    r"\bMISO\b",
    r"\bSPP\b",
    r"\bNYISO\b",
    r"\bISO-NE\b",
)


CANONICAL_ENTITIES = {
    "np15": "NP-15",
    "np-15": "NP-15",
    "sp15": "SP-15",
    "sp-15": "SP-15",
    "henry hub": "Henry Hub",
    "brent": "Brent",
    "wti": "WTI",
    "diablo canyon": "Diablo Canyon",
    "freeport lng": "Freeport LNG",
    "ercot": "ERCOT",
    "caiso": "CAISO",
    "pjm": "PJM",
    "miso": "MISO",
    "spp": "SPP",
    "nyiso": "NYISO",
    "iso-ne": "ISO-NE",
}


def _classify(
    text: str,
    patterns: tuple[
        tuple[object, tuple[str, ...]],
        ...
    ],
    default: object,
) -> object:
    lowered = text.lower()

    best_classification = default
    best_score = 0
    best_longest_term = 0

    for classification, terms in patterns:
        matches = [
            term
            for term in terms
            if term in lowered
        ]

        if not matches:
            continue

        score = len(matches)
        longest_term = max(
            len(term)
            for term in matches
        )

        if (
            score > best_score
            or (
                score == best_score
                and longest_term > best_longest_term
            )
        ):
            best_classification = classification
            best_score = score
            best_longest_term = longest_term

    return best_classification


def _entities(question: str) -> tuple[str, ...]:
    found: list[str] = []

    for pattern in ENTITY_PATTERNS:
        for match in re.findall(
            pattern,
            question,
            flags=re.IGNORECASE,
        ):
            raw = str(match).strip()
            normalized = CANONICAL_ENTITIES.get(
                raw.lower(),
                raw,
            )

            if normalized not in found:
                found.append(normalized)

    return tuple(found)


def classify_energy_question(
    question: str,
) -> EnergyClassification:
    commodity = _classify(
        question,
        COMMODITY_PATTERNS,
        EnergyCommodity.UNKNOWN,
    )

    topic = _classify(
        question,
        TOPIC_PATTERNS,
        EnergyTopic.GENERAL,
    )

    geography = _classify(
        question,
        GEOGRAPHY_PATTERNS,
        GeographicScope.UNKNOWN,
    )

    tokens = tuple(
        token.lower()
        for token in re.findall(
            r"[A-Za-z0-9_-]+",
            question,
        )
        if len(token) >= 3
    )

    return EnergyClassification(
        commodity=commodity,
        topic=topic,
        geography=geography,
        entities=_entities(question),
        keywords=tokens,
    )
