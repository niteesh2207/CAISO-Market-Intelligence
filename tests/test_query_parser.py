from datetime import datetime
from zoneinfo import ZoneInfo

from market_intelligence.models.query import Market, QueryIntent
from market_intelligence.routing.parser import parse_market_query


def test_np15_yesterday_query_is_resolved_in_pacific_time():
    now = datetime(
        2026,
        8,
        3,
        9,
        0,
        tzinfo=ZoneInfo("America/Los_Angeles"),
    )

    query = parse_market_query(
        "What prices did NP-15 settle for yesterday?",
        now=now,
    )

    assert query.market == Market.CAISO
    assert query.intent == QueryIntent.PRICE
    assert query.requested_date.isoformat() == "2026-08-02"
    assert query.nodes == ["NP-15"]


def test_diablo_query_is_classified_as_generation():
    query = parse_market_query(
        "Is Diablo Canyon running at full capacity?"
    )

    assert query.market == Market.CAISO
    assert query.intent == QueryIntent.GENERATION
