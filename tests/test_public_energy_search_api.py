from fastapi.testclient import TestClient

import app as application
from market_intelligence.routing.universal_energy_router import (
    EnergyDomain,
)
from market_intelligence.service.universal_orchestrator import (
    UniversalAnswer,
    UniversalAnswerStatus,
    UniversalSource,
)


client = TestClient(application.app)


class FakeOrchestrator:
    def answer(self, question):
        return UniversalAnswer(
            question=question,
            status=UniversalAnswerStatus.ANSWERED,
            domain=EnergyDomain.ELECTRICITY_MARKETS,
            direct_answer=(
                "EIA reported CAISO demand of "
                "37,944 megawatthours."
            ),
            simple_explanation=(
                "The value comes from EIA "
                "Form EIA-930."
            ),
            confidence="high",
            sources=(
                UniversalSource(
                    title=(
                        "EIA U.S. Electric System "
                        "Operating Data"
                    ),
                    url=(
                        "https://www.eia.gov/"
                        "opendata/bulk/EBA.zip"
                    ),
                    provider_id="eia_bulk_eba",
                    is_primary=True,
                ),
            ),
            evidence_payload={
                "value": 37944,
                "source_unit": "megawatthours",
            },
        )


class MissingCacheOrchestrator:
    def answer(self, question):
        raise FileNotFoundError(
            "EBA cache not found."
        )


class FailedStructuredExecutor:
    def answer(self, question):
        raise RuntimeError(
            "Structured executor failed."
        )


def test_status_endpoint():
    response = client.get("/api/status")

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["service"] == (
        "CAISO Market Intelligence"
    )
    assert payload["version"] == "4.0.0"
    assert payload[
        "universal_orchestrator"
    ] is True
    assert isinstance(
        payload["eia_cache_available"],
        bool,
    )
    assert isinstance(
        payload["openai_configured"],
        bool,
    )


def test_capabilities_endpoint():
    response = client.get(
        "/api/capabilities"
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) >= 4

    assert any(
        item["capability"]
        == "CAISO market prices"
        for item in payload
    )

    assert any(
        item["controlling_source"]
        == "EIA Form EIA-930"
        for item in payload
    )


def test_search_endpoint(monkeypatch):
    monkeypatch.setattr(
        application,
        "_universal_orchestrator",
        FakeOrchestrator(),
    )

    response = client.post(
        "/api/search",
        json={
            "question": (
                "What is CAISO demand right now?"
            ),
            "allow_web_fallback": False,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "answered"
    assert payload["domain"] == (
        "electricity_markets"
    )
    assert payload["confidence"] == "high"
    assert payload["evidence"]["value"] == 37944
    assert payload["sources"][0][
        "provider"
    ] == "eia_bulk_eba"
    assert payload["sources"][0][
        "primary"
    ] is True


def test_search_rejects_empty_question():
    response = client.post(
        "/api/search",
        json={
            "question": "",
        },
    )

    assert response.status_code == 422


def test_search_rejects_one_character_question():
    response = client.post(
        "/api/search",
        json={
            "question": "x",
        },
    )

    assert response.status_code == 422


def test_missing_eia_cache_returns_503(
    monkeypatch,
):
    monkeypatch.setattr(
        application,
        "_universal_orchestrator",
        MissingCacheOrchestrator(),
    )

    response = client.post(
        "/api/search",
        json={
            "question": (
                "What is CAISO demand right now?"
            ),
            "allow_web_fallback": False,
        },
    )

    assert response.status_code == 503

    payload = response.json()["detail"]

    assert payload["code"] == (
        "EIA_CACHE_NOT_AVAILABLE"
    )
    assert "remediation" in payload


def test_structured_executor_failure_returns_502(
    monkeypatch,
):
    monkeypatch.setattr(
        application,
        "_universal_orchestrator",
        FailedStructuredExecutor(),
    )

    response = client.post(
        "/api/search",
        json={
            "question": (
                "What is CAISO demand right now?"
            ),
            "allow_web_fallback": False,
        },
    )

    assert response.status_code == 502

    payload = response.json()["detail"]

    assert payload["code"] == (
        "STRUCTURED_EXECUTOR_FAILURE"
    )


def test_structured_failure_uses_public_research_when_enabled(
    monkeypatch,
):
    monkeypatch.setattr(
        application,
        "_universal_orchestrator",
        FailedStructuredExecutor(),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    class PublicResult:
        answer = "Current CAISO demand is reported by CAISO. [1]"
        confidence = "medium"
        limitations = ()
        searched_at = "2026-08-06T18:00:00+00:00"
        discovered_results = 3
        retrieved_pages = 2
        sources = ()

    class PublicAgent:
        def answer(self, question, *, allowed_domains):
            assert question
            assert "caiso.com" in allowed_domains
            return PublicResult()

    monkeypatch.setattr(
        application,
        "_public_web_agent",
        PublicAgent(),
    )

    response = client.post(
        "/api/search",
        json={
            "question": "What is CAISO demand right now?",
            "allow_web_fallback": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["used_web_fallback"] is True
    assert payload["evidence"]["retrieved_pages"] == 2
