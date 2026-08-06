from market_intelligence.research.models import (
    ResearchAnswer,
    ResearchSource,
    SourceTier,
)
from market_intelligence.routing.universal_energy_router import (
    EnergyDomain,
)
from market_intelligence.service.universal_orchestrator import (
    UniversalAnswer,
    UniversalAnswerStatus,
    UniversalResearchOrchestrator,
)


class FakeResearchAgent:
    def __init__(
        self,
        result: ResearchAnswer,
    ) -> None:
        self.result = result
        self.calls = 0
        self.questions: list[str] = []

    def answer(
        self,
        question: str,
    ) -> ResearchAnswer:
        self.calls += 1
        self.questions.append(question)
        return self.result


class ExplodingResearchAgent:
    def __init__(self) -> None:
        self.calls = 0

    def answer(self, question: str):
        self.calls += 1
        raise RuntimeError(
            "simulated research failure"
        )


class FakeNuclearAgent:
    def __init__(
        self,
        result: UniversalAnswer,
    ) -> None:
        self.result = result
        self.calls = 0

    def answer(
        self,
        question: str,
    ) -> UniversalAnswer:
        self.calls += 1
        return self.result


def answered_research_result() -> ResearchAnswer:
    return ResearchAnswer(
        status="answered",
        answer=(
            "Henry Hub prices rose because the "
            "retrieved evidence showed tighter "
            "market conditions."
        ),
        explanation=(
            "The conclusion was synthesized from "
            "the retrieved energy-market sources."
        ),
        confidence="medium",
        as_of="2026-08-04T18:00:00+00:00",
        sources=(
            ResearchSource(
                provider="eia.gov",
                title="Natural Gas Market Update",
                url=(
                    "https://www.eia.gov/"
                    "naturalgas/"
                ),
                excerpt=(
                    "Official natural-gas "
                    "market evidence."
                ),
                primary=True,
                source_tier=(
                    SourceTier.CONTROLLING
                ),
                published_at=(
                    "2026-08-04T00:00:00Z"
                ),
                retrieved_at=(
                    "2026-08-04T18:00:00Z"
                ),
            ),
        ),
        limitations=(),
        evidence={
            "retrieved_sources": 1,
        },
    )


def test_unsupported_energy_question_uses_research():
    research = FakeResearchAgent(
        answered_research_result()
    )

    orchestrator = UniversalResearchOrchestrator(
        research_agent=research,
    )

    result = orchestrator.answer(
        "Why did Henry Hub natural gas prices rise?"
    )

    assert research.calls == 1
    assert result.status == (
        UniversalAnswerStatus.ANSWERED
    )
    assert result.domain == EnergyDomain.NATURAL_GAS
    assert result.confidence == "medium"
    assert len(result.sources) == 1
    assert result.sources[0].provider_id == "eia.gov"
    assert result.sources[0].is_primary is True
    assert (
        result.evidence_payload[
            "retrieved_sources"
        ]
        == 1
    )


def test_structured_nuclear_answer_has_precedence():
    research = FakeResearchAgent(
        answered_research_result()
    )

    nuclear_result = UniversalAnswer(
        question=(
            "Is Diablo Canyon running "
            "at full capacity?"
        ),
        status=UniversalAnswerStatus.ANSWERED,
        domain=EnergyDomain.NUCLEAR,
        direct_answer=(
            "The structured NRC executor answered."
        ),
        simple_explanation=(
            "Official NRC evidence was used."
        ),
        confidence="high",
    )

    nuclear = FakeNuclearAgent(
        nuclear_result
    )

    orchestrator = UniversalResearchOrchestrator(
        nuclear_agent=nuclear,
        research_agent=research,
    )

    result = orchestrator.answer(
        "Is Diablo Canyon running at full capacity?"
    )

    assert nuclear.calls == 1
    assert research.calls == 0
    assert result is nuclear_result


def test_non_energy_question_does_not_use_research():
    research = FakeResearchAgent(
        answered_research_result()
    )

    orchestrator = UniversalResearchOrchestrator(
        research_agent=research,
    )

    result = orchestrator.answer(
        "Who won the football match?"
    )

    assert research.calls == 0
    assert result.status == (
        UniversalAnswerStatus.NEEDS_CLARIFICATION
    )
    assert result.domain == EnergyDomain.UNKNOWN


def test_research_unavailable_is_held_safely():
    research = FakeResearchAgent(
        ResearchAnswer(
            status="research_unavailable",
            answer=(
                "I could not retrieve enough "
                "verifiable source material."
            ),
            explanation=(
                "No usable source pages were returned."
            ),
            confidence="insufficient",
            as_of=(
                "2026-08-04T18:00:00+00:00"
            ),
            sources=(),
            limitations=(
                "Discovery provider unavailable.",
            ),
            evidence={
                "retrieved_sources": 0,
            },
        )
    )

    orchestrator = UniversalResearchOrchestrator(
        research_agent=research,
    )

    result = orchestrator.answer(
        "What is the latest status of an LNG project?"
    )

    assert research.calls == 1
    assert result.status == UniversalAnswerStatus.HELD
    assert result.confidence == "insufficient"
    assert result.limitations
    assert result.sources == ()


def test_research_exception_is_contained():
    research = ExplodingResearchAgent()

    orchestrator = UniversalResearchOrchestrator(
        research_agent=research,
    )

    result = orchestrator.answer(
        "Why did Henry Hub natural gas prices rise?"
    )

    assert research.calls == 1
    assert result.status == UniversalAnswerStatus.HELD
    assert result.confidence == "insufficient"
    assert "RuntimeError" in result.limitations[0]
