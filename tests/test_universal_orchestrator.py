from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from market_intelligence.retrieval.models import (
    RetrievedRecord,
    RetrievalMethod,
)
from market_intelligence.routing.universal_energy_router import (
    EnergyDomain,
)
from market_intelligence.service.universal_orchestrator import (
    UniversalAnswer,
    UniversalAnswerStatus,
    UniversalResearchOrchestrator,
)


def caiso_record(
    *,
    primary=True,
    complete=True,
):
    return RetrievedRecord(
        provider_id="caiso_oasis",
        method=RetrievalMethod.STRUCTURED_API,
        source_title="CAISO OASIS LMP",
        source_url=(
            "https://oasis.caiso.com/"
            "oasisapi/SingleZip"
        ),
        observed_at=datetime.now(timezone.utc),
        published_at=None,
        retrieved_at=datetime.now(timezone.utc),
        payload={
            "unit": "USD/MWh",
            "value": 42.81,
            "complete_coverage": complete,
            "actual_interval_count": 24,
            "market": "CAISO DAM NP-15",
            "timezone": "America/Los_Angeles",
        },
        is_primary=primary,
        authority_rank=1,
        metadata={
            "complete_coverage": complete,
            "has_unit": True,
            "has_market_context": True,
            "has_timezone": True,
        },
    )


class FakeCaisoAgent:
    def __init__(
        self,
        *,
        status="answered",
        record=None,
    ):
        self.status = status
        self.record = (
            record
            if record is not None
            else caiso_record()
        )
        self.questions = []

    def answer(self, question):
        self.questions.append(question)

        if self.status == "needs_clarification":
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

        return SimpleNamespace(
            status=SimpleNamespace(
                value="answered"
            ),
            direct_answer=(
                "NP-15 DAM averaged $42.81/MWh."
            ),
            simple_explanation=(
                "The official CAISO result contained "
                "24 validated intervals."
            ),
            clarification_options=(),
            record=self.record,
        )


class FakeNuclearAgent:
    def answer(self, question):
        return UniversalAnswer(
            question=question,
            status=UniversalAnswerStatus.ANSWERED,
            domain=EnergyDomain.NUCLEAR,
            direct_answer=(
                "Diablo Canyon was reported at full power."
            ),
            simple_explanation=(
                "Both units were reported at 100%."
            ),
            confidence="high",
        )


def test_caiso_question_dispatches_to_live_agent():
    caiso = FakeCaisoAgent()

    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=caiso,
        nuclear_agent=FakeNuclearAgent(),
    )

    result = orchestrator.answer(
        "What were NP-15 day-ahead prices "
        "on August 2, 2026?"
    )

    assert result.status == (
        UniversalAnswerStatus.ANSWERED
    )
    assert result.domain == (
        EnergyDomain.ELECTRICITY_MARKETS
    )
    assert result.confidence == "high"
    assert len(result.sources) == 1
    assert result.sources[0].provider_id == (
        "caiso_oasis"
    )
    assert caiso.questions


def test_ambiguous_caiso_question_requests_clarification():
    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=FakeCaisoAgent(
            status="needs_clarification"
        ),
        nuclear_agent=FakeNuclearAgent(),
    )

    result = orchestrator.answer(
        "What prices did NP-15 settle for yesterday?"
    )

    assert result.status == (
        UniversalAnswerStatus.NEEDS_CLARIFICATION
    )
    assert result.clarification_options


def test_incomplete_caiso_day_is_held():
    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=FakeCaisoAgent(
            record=caiso_record(
                complete=False
            )
        ),
        nuclear_agent=FakeNuclearAgent(),
    )

    result = orchestrator.answer(
        "What were NP-15 day-ahead prices "
        "on August 2, 2026?"
    )

    assert result.status == UniversalAnswerStatus.HELD
    assert result.confidence == "insufficient"


def test_non_primary_caiso_evidence_is_held():
    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=FakeCaisoAgent(
            record=caiso_record(
                primary=False
            )
        ),
        nuclear_agent=FakeNuclearAgent(),
    )

    result = orchestrator.answer(
        "What were NP-15 day-ahead prices "
        "on August 2, 2026?"
    )

    assert result.status == UniversalAnswerStatus.HELD


def test_nuclear_question_dispatches_to_nuclear_agent():
    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=FakeCaisoAgent(),
        nuclear_agent=FakeNuclearAgent(),
    )

    result = orchestrator.answer(
        "Is Diablo Canyon running at full capacity today?"
    )

    assert result.status == (
        UniversalAnswerStatus.ANSWERED
    )
    assert result.domain == EnergyDomain.NUCLEAR


def test_unimplemented_domain_returns_research_plan():
    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=FakeCaisoAgent(),
        nuclear_agent=FakeNuclearAgent(),
    )

    result = orchestrator.answer(
        "Why did Henry Hub natural gas prices rise?"
    )

    assert result.status == (
        UniversalAnswerStatus.RESEARCH_REQUIRED
    )
    assert result.domain == EnergyDomain.NATURAL_GAS
    assert result.evidence_payload[
        "planned_providers"
    ]
    assert "eia_api" in {
        item["provider_id"]
        for item in result.evidence_payload[
            "planned_providers"
        ]
    }


def test_weather_question_returns_multi_source_plan():
    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=FakeCaisoAgent(),
        nuclear_agent=FakeNuclearAgent(),
    )

    result = orchestrator.answer(
        "Will tomorrow's Texas heat affect ERCOT demand?"
    )

    assert result.status == (
        UniversalAnswerStatus.RESEARCH_REQUIRED
    )
    assert result.domain == EnergyDomain.WEATHER

    providers = {
        item["provider_id"]
        for item in result.evidence_payload[
            "planned_providers"
        ]
    }

    assert "noaa_nws" in providers
    assert "iso_rto_operational_data" in providers


def test_non_energy_question_requests_clarification():
    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=FakeCaisoAgent(),
        nuclear_agent=FakeNuclearAgent(),
    )

    result = orchestrator.answer(
        "Who won the tennis match?"
    )

    assert result.status == (
        UniversalAnswerStatus.NEEDS_CLARIFICATION
    )
    assert result.domain == EnergyDomain.UNKNOWN


def test_empty_question_is_rejected():
    orchestrator = UniversalResearchOrchestrator(
        caiso_agent=FakeCaisoAgent(),
        nuclear_agent=FakeNuclearAgent(),
    )

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        orchestrator.answer("   ")
