from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

import app as app_module
from market_intelligence.research.cited_synthesizer import (
    CitedClaim,
    CitedResearchAnswer,
    CitedSource,
)
from market_intelligence.routing.universal_energy_router import (
    EnergyDomain,
)
from market_intelligence.service.universal_orchestrator import (
    UniversalAnswer,
    UniversalAnswerStatus,
)


client = TestClient(app_module.app)


@dataclass
class FakeUniversalOrchestrator:
    result: UniversalAnswer
    calls: int = 0

    def answer(
        self,
        question: str,
    ) -> UniversalAnswer:
        self.calls += 1
        return self.result


@dataclass
class FakeCitedResearchService:
    result: CitedResearchAnswer
    calls: int = 0

    def answer(
        self,
        question: str,
    ) -> CitedResearchAnswer:
        self.calls += 1
        return self.result


def structured_answer() -> UniversalAnswer:
    return UniversalAnswer(
        question="What is CAISO demand?",
        status=UniversalAnswerStatus.ANSWERED,
        domain=EnergyDomain.ELECTRICITY_MARKETS,
        direct_answer="CAISO demand is 30,000 MW.",
        simple_explanation=(
            "The value came from structured "
            "operating data."
        ),
        confidence="high",
    )


def research_required_answer() -> UniversalAnswer:
    return UniversalAnswer(
        question=(
            "Where are data centers "
            "in SDG&E territory?"
        ),
        status=(
            UniversalAnswerStatus
            .RESEARCH_REQUIRED
        ),
        domain=EnergyDomain.ELECTRICITY_MARKETS,
        direct_answer="",
        simple_explanation=(
            "Validated research is required."
        ),
        confidence="insufficient",
    )


def cited_answer(
    *,
    status: str = "answered",
) -> CitedResearchAnswer:
    return CitedResearchAnswer(
        status=status,
        question=(
            "Where are data centers "
            "in SDG&E territory?"
        ),
        direct_answer=(
            "Public evidence identifies a "
            "major-load project in SDG&E "
            "territory."
            if status == "answered"
            else ""
        ),
        explanation=(
            "The conclusion is based on the "
            "cited utility document."
            if status == "answered"
            else (
                "The available evidence was "
                "insufficient."
            )
        ),
        confidence=(
            "medium"
            if status == "answered"
            else "insufficient"
        ),
        as_of="2026-08-05T20:00:00+00:00",
        claims=(
            (
                CitedClaim(
                    text=(
                        "A major-load project "
                        "appears in SDG&E "
                        "territory."
                    ),
                    source_ids=(1,),
                    claim_type="fact",
                ),
            )
            if status == "answered"
            else ()
        ),
        sources=(
            (
                CitedSource(
                    source_id=1,
                    title="Utility Filing",
                    url=(
                        "https://www.sdge.com/"
                        "utility-filing"
                    ),
                    provider="SDG&E",
                    source_tier="primary",
                    retrieved_at=(
                        "2026-08-05T19:00:00+00:00"
                    ),
                ),
            )
            if status == "answered"
            else ()
        ),
        limitations=(
            "Public information may be incomplete.",
        ),
        evidence_summary={
            "accepted_documents": (
                1
                if status == "answered"
                else 0
            ),
        },
    )


def test_structured_answer_retains_precedence(
    monkeypatch,
):
    orchestrator = FakeUniversalOrchestrator(
        structured_answer()
    )
    research = FakeCitedResearchService(
        cited_answer()
    )

    monkeypatch.setattr(
        app_module,
        "_universal_orchestrator",
        orchestrator,
    )
    monkeypatch.setattr(
        app_module,
        "_cited_research_service",
        research,
    )

    response = client.post(
        "/api/search",
        json={
            "question": (
                "What is CAISO demand?"
            ),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "answered"
    assert payload["used_web_fallback"] is False
    assert orchestrator.calls == 1
    assert research.calls == 0


def test_research_required_uses_cited_service(
    monkeypatch,
):
    orchestrator = FakeUniversalOrchestrator(
        research_required_answer()
    )
    research = FakeCitedResearchService(
        cited_answer()
    )

    monkeypatch.setattr(
        app_module,
        "_universal_orchestrator",
        orchestrator,
    )
    monkeypatch.setattr(
        app_module,
        "_cited_research_service",
        research,
    )

    response = client.post(
        "/api/search",
        json={
            "question": (
                "Where are data centers "
                "in SDG&E territory?"
            ),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "answered"
    assert payload["used_web_fallback"] is True
    assert payload["claims"][0][
        "source_ids"
    ] == [1]
    assert payload["sources"][0][
        "source_id"
    ] == 1
    assert research.calls == 1


def test_web_fallback_can_be_disabled(
    monkeypatch,
):
    orchestrator = FakeUniversalOrchestrator(
        research_required_answer()
    )
    research = FakeCitedResearchService(
        cited_answer()
    )

    monkeypatch.setattr(
        app_module,
        "_universal_orchestrator",
        orchestrator,
    )
    monkeypatch.setattr(
        app_module,
        "_cited_research_service",
        research,
    )

    response = client.post(
        "/api/search",
        json={
            "question": (
                "Where are data centers "
                "in SDG&E territory?"
            ),
            "allow_web_fallback": False,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["status"]
        == "research_required"
    )
    assert payload["used_web_fallback"] is False
    assert research.calls == 0


def test_held_cited_response_is_preserved(
    monkeypatch,
):
    orchestrator = FakeUniversalOrchestrator(
        research_required_answer()
    )
    research = FakeCitedResearchService(
        cited_answer(status="held")
    )

    monkeypatch.setattr(
        app_module,
        "_universal_orchestrator",
        orchestrator,
    )
    monkeypatch.setattr(
        app_module,
        "_cited_research_service",
        research,
    )

    response = client.post(
        "/api/search",
        json={
            "question": (
                "Where are data centers "
                "in SDG&E territory?"
            ),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "held"
    assert payload["used_web_fallback"] is True
    assert payload["answer"] == ""
    assert research.calls == 1
