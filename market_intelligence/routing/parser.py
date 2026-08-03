from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from market_intelligence.models.query import (
    Market,
    MarketQuery,
    QueryIntent,
)


MARKET_PATTERNS = {
    Market.CAISO: (
        "caiso",
        "np15",
        "np-15",
        "sp15",
        "sp-15",
        "diablo canyon",
    ),
    Market.ERCOT: ("ercot", "north hub", "houston hub"),
    Market.PJM: ("pjm", "western hub"),
    Market.MISO: ("miso",),
    Market.SPP: ("spp", "south hub", "north hub"),
    Market.NYISO: ("nyiso",),
    Market.ISO_NE: ("iso-ne", "isone", "new england"),
    Market.WEST: ("bpa", "mid-c", "palo verde", "western"),
}


def _market(question: str) -> Market:
    q = question.lower()

    for market, patterns in MARKET_PATTERNS.items():
        if any(pattern in q for pattern in patterns):
            return market

    return Market.GENERAL


def _intent(question: str) -> QueryIntent:
    q = question.lower()

    rules = (
        (
            QueryIntent.PRICE,
            (
                "price",
                "lmp",
                "settle",
                "settlement",
                "day-ahead",
                "day ahead",
                "real-time",
                "real time",
            ),
        ),
        (
            QueryIntent.GENERATION,
            (
                "generation",
                "capacity",
                "running",
                "output",
                "diablo",
                "nuclear",
                "unit",
            ),
        ),
        (
            QueryIntent.OUTAGE,
            ("outage", "offline", "derate", "trip"),
        ),
        (
            QueryIntent.CONGESTION,
            (
                "constraint",
                "congestion",
                "binding",
                "shadow price",
                "flowgate",
            ),
        ),
        (
            QueryIntent.GAS,
            ("gas", "pipeline", "citygate", "storage"),
        ),
        (
            QueryIntent.WEATHER,
            ("weather", "temperature", "heat", "wind forecast"),
        ),
        (
            QueryIntent.REGULATORY,
            ("ferc", "cpuc", "tariff", "filing", "rule"),
        ),
        (
            QueryIntent.NEWS,
            ("news", "latest", "what happened"),
        ),
    )

    for intent, patterns in rules:
        if any(pattern in q for pattern in patterns):
            return intent

    return QueryIntent.GENERAL


def _nodes(question: str) -> list[str]:
    candidates = re.findall(
        r"\b(?:NP-?15|SP-?15|ZP26|TH_[A-Z0-9_]+)\b",
        question,
        flags=re.IGNORECASE,
    )

    return list(
        dict.fromkeys(
            candidate.upper().replace("NP15", "NP-15").replace(
                "SP15",
                "SP-15",
            )
            for candidate in candidates
        )
    )


def parse_market_query(
    question: str,
    *,
    now: datetime | None = None,
) -> MarketQuery:
    timezone = ZoneInfo("America/Los_Angeles")
    current = now or datetime.now(timezone)

    q = question.lower()
    requested_date = None

    if "yesterday" in q:
        requested_date = (current - timedelta(days=1)).date()
    elif "today" in q:
        requested_date = current.date()

    return MarketQuery(
        raw_question=question.strip(),
        market=_market(question),
        intent=_intent(question),
        timezone="America/Los_Angeles",
        requested_date=requested_date,
        nodes=_nodes(question),
    )
