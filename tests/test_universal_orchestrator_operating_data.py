from datetime import datetime, timezone
from types import SimpleNamespace


from market_intelligence.connectors.eia_eba import (
    EbaMetric,
)
from market_intelligence.service.universal_orchestrator import (
    UniversalAnswerStatus,
    UniversalResearchOrchestrator,
)


class FakeOperatingDataAgent:
    def __init__(
        self,
        *,
        status="answered",
    ):
        self.status = status
        self.questions = []

    def answer(self, question):
        self.questions.append(question)

        if self.status == "needs_clarification":
            return SimpleNamespace(
                status=SimpleNamespace(
                    value="needs_clarification"
                ),
                balancing_authority=None,
                metric=None,
                direct_answer=(
                    "Please specify the balancing "
                    "authority and metric."
                ),
                simple_explanation=(
                    "Supported metrics include demand, "
                    "forecast, generation and interchange."
                ),
                source_url=None,
                observation_timestamp_utc=None,
                value=None,
                source_unit=None,
                equivalent_average_mw=None,
                age_hours=None,
            )

        return SimpleNamespace(
            status=SimpleNamespace(
                value=self.status
            ),
            balancing_authority="CAISO",
            metric=EbaMetric.DEMAND,
            direct_answer=(
                "EIA reported CAISO demand of "
                "37,944 megawatthours."
            ),
            simple_explanation=(
                "The value comes from EIA Form "
                "EIA-930 series EBA.CISO-ALL.D.H."
            ),
            source_url=(
                "https://www.eia.gov/"
                "opendata/bulk/EBA.zip"
            ),
            observation_timestamp_utc=datetime(
                2026,
                8,
                3,
                19,
                tzinfo=timezone.utc,
            ),
            value=37944.0,
            source_unit="megawatthours",
            equivalent_average_mw=37944.0,
            age_hours=2.0,
        )


class UnexpectedCaisoAgent:
    def answer(self, question):
        raise AssertionError(
            "CAISO price agent should not receive "
            "an operating-data question."
        )


def test_caiso_demand_dispatches_to_eia_operating_data():
    operating = FakeOperatingDataAgent()

    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=UnexpectedCaisoAgent(),
        operating_data_agent=operating,
    )

    result = orchestrator.answer(
        "What is CAISO demand right now?"
    )

    assert result.status == (
        UniversalAnswerStatus.ANSWERED
    )
    assert result.confidence == "high"
    assert result.sources[0].provider_id == (
        "eia_bulk_eba"
    )
    assert result.evidence_payload[
        "balancing_authority"
    ] == "CAISO"
    assert result.evidence_payload["metric"] == "D"
    assert result.evidence_payload["value"] == 37944.0
    assert operating.questions


def test_stale_operating_data_is_labeled():
    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=UnexpectedCaisoAgent(),
        operating_data_agent=(
            FakeOperatingDataAgent(
                status="stale"
            )
        ),
    )

    result = orchestrator.answer(
        "What is CAISO demand right now?"
    )

    assert result.status == (
        UniversalAnswerStatus.ANSWERED
    )
    assert result.confidence == "medium"
    assert result.evidence_payload["stale"] is True
    assert result.limitations


def test_np15_price_does_not_route_to_eia_operating_data():
    operating = FakeOperatingDataAgent()

    class FakePriceAgent:
        def answer(self, question):
            return SimpleNamespace(
                status=SimpleNamespace(
                    value="needs_clarification"
                ),
                direct_answer=(
                    "Please specify the CAISO market."
                ),
                simple_explanation=(
                    "DAM, FMM and RTM are separate."
                ),
                clarification_options=(
                    "Day-ahead",
                    "Fifteen-minute",
                    "Real-time",
                ),
                record=None,
            )

    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=FakePriceAgent(),
        operating_data_agent=operating,
    )

    result = orchestrator.answer(
        "What prices did NP-15 settle for yesterday?"
    )

    assert result.status == (
        UniversalAnswerStatus.NEEDS_CLARIFICATION
    )
    assert not operating.questions
