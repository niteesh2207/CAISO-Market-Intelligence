from datetime import datetime, timezone

import pytest

from market_intelligence.connectors.caiso_price_query import (
    CaisoMarket,
)
from market_intelligence.retrieval.models import (
    RetrievedRecord,
    RetrievalMethod,
)
from market_intelligence.service.caiso_price_agent import (
    CaisoPriceAgent,
    CaisoPriceAgentStatus,
)


class FakeExecutor:
    def __init__(self) -> None:
        self.queries = []

    def execute_to_record(
        self,
        query,
        *,
        require_complete_coverage=True,
    ):
        self.queries.append(query)

        return RetrievedRecord(
            provider_id="caiso_oasis",
            method=RetrievalMethod.STRUCTURED_API,
            source_title="CAISO OASIS LMP",
            source_url=query.url,
            observed_at=query.date_window.utc_end,
            published_at=None,
            retrieved_at=datetime.now(timezone.utc),
            payload={
                "direct_answer": (
                    f"{query.location.display_name} "
                    f"{query.market.value} LMP averaged "
                    "$42.81/MWh."
                ),
                "simple_explanation": (
                    "The official result contained all "
                    "required intervals."
                ),
                "value": 42.81,
                "unit": "USD/MWh",
                "market": (
                    f"CAISO {query.market.value} "
                    f"{query.location.display_name}"
                ),
                "timezone": "America/Los_Angeles",
                "interval": "hourly",
                "actual_interval_count": 24,
                "complete_coverage": True,
            },
            is_primary=True,
            authority_rank=1,
            metadata={
                "complete_coverage": True,
                "has_unit": True,
                "has_market_context": True,
                "has_timezone": True,
            },
        )


def test_explicit_np15_dam_question_is_answered():
    executor = FakeExecutor()
    agent = CaisoPriceAgent(executor=executor)

    result = agent.answer(
        "What were NP-15 day-ahead prices yesterday?"
    )

    assert result.status == (
        CaisoPriceAgentStatus.ANSWERED
    )
    assert result.market == CaisoMarket.DAY_AHEAD
    assert result.location.display_name == "NP-15"
    assert result.record is not None
    assert result.record.is_primary is True
    assert len(executor.queries) == 1


def test_ambiguous_market_requests_clarification():
    executor = FakeExecutor()
    agent = CaisoPriceAgent(executor=executor)

    result = agent.answer(
        "What prices did NP-15 settle for yesterday?"
    )

    assert result.status == (
        CaisoPriceAgentStatus.NEEDS_CLARIFICATION
    )
    assert result.market == CaisoMarket.UNSPECIFIED
    assert result.record is None
    assert len(result.clarification_options) == 4
    assert executor.queries == []


def test_sp15_real_time_question_is_resolved():
    executor = FakeExecutor()
    agent = CaisoPriceAgent(executor=executor)

    result = agent.answer(
        "What were SP-15 real-time prices "
        "on 2026-08-02?"
    )

    assert result.status == (
        CaisoPriceAgentStatus.ANSWERED
    )
    assert result.market == CaisoMarket.REAL_TIME
    assert result.location.display_name == "SP-15"

    query = executor.queries[0]

    assert query.date_window.market_date.isoformat() == (
        "2026-08-02"
    )


def test_fmm_question_is_resolved():
    executor = FakeExecutor()
    agent = CaisoPriceAgent(executor=executor)

    result = agent.answer(
        "Give me NP-15 fifteen-minute prices "
        "for 2026-08-02."
    )

    assert result.market == (
        CaisoMarket.FIFTEEN_MINUTE
    )
    assert result.status == (
        CaisoPriceAgentStatus.ANSWERED
    )


def test_result_preserves_source_link():
    executor = FakeExecutor()
    agent = CaisoPriceAgent(executor=executor)

    result = agent.answer(
        "What was the NP-15 day-ahead LMP "
        "on 2026-08-02?"
    )

    assert result.source_url is not None
    assert result.source_url.startswith(
        "https://oasis.caiso.com/"
    )


def test_empty_question_is_rejected():
    agent = CaisoPriceAgent(
        executor=FakeExecutor()
    )

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        agent.answer("   ")


def test_unknown_location_is_rejected():
    agent = CaisoPriceAgent(
        executor=FakeExecutor()
    )

    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        agent.answer(
            "What were Unknown Hub day-ahead "
            "prices yesterday?"
        )


def test_answer_uses_verified_numeric_context():
    executor = FakeExecutor()
    agent = CaisoPriceAgent(executor=executor)

    result = agent.answer(
        "What was the NP-15 day-ahead price "
        "on 2026-08-02?"
    )

    assert result.record is not None
    assert result.record.payload["unit"] == "USD/MWh"
    assert result.record.payload["timezone"] == (
        "America/Los_Angeles"
    )
    assert (
        result.record.metadata["complete_coverage"]
        is True
    )
