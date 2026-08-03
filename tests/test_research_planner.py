from datetime import date

from market_intelligence.models.query import (
    Market,
    MarketQuery,
    QueryIntent,
)
from market_intelligence.routing.planner import (
    ResearchMode,
    build_research_plan,
)


def test_np15_price_query_requires_oasis():
    query = MarketQuery(
        raw_question=(
            "What prices did NP-15 settle for yesterday?"
        ),
        market=Market.CAISO,
        intent=QueryIntent.PRICE,
        requested_date=date(2026, 8, 2),
        nodes=["NP-15"],
    )

    plan = build_research_plan(query)

    assert plan.mode == ResearchMode.STRUCTURED_FIRST
    assert plan.requires_structured_data is True
    assert "caiso_oasis" in plan.required_connectors
    assert plan.warnings == []


def test_ambiguous_caiso_price_query_is_flagged():
    query = MarketQuery(
        raw_question="What did CAISO prices settle at?",
        market=Market.CAISO,
        intent=QueryIntent.PRICE,
    )

    plan = build_research_plan(query)

    assert len(plan.warnings) == 2


def test_diablo_query_requires_nrc_and_web_context():
    query = MarketQuery(
        raw_question=(
            "Is Diablo Canyon running at full capacity?"
        ),
        market=Market.CAISO,
        intent=QueryIntent.GENERATION,
        assets=["Diablo Canyon"],
    )

    plan = build_research_plan(query)

    assert plan.mode == ResearchMode.HYBRID
    assert "nrc_reactor_status" in plan.required_connectors
    assert plan.minimum_primary_sources == 1
    assert plan.minimum_total_sources == 2
