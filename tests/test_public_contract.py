from __future__ import annotations

import logging
import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

import app as application
from market_intelligence.routing.universal_energy_router import EnergyDomain
from market_intelligence.service.universal_orchestrator import (
    UniversalAnswer,
    UniversalAnswerStatus,
)

client = TestClient(application.app)


class FakeOrchestrator:
    def __init__(self, answer: UniversalAnswer) -> None:
        self._answer = answer

    def answer(self, question: str) -> UniversalAnswer:
        return self._answer


def research_required() -> UniversalAnswer:
    return UniversalAnswer(
        question="Why did gas prices rise?",
        status=UniversalAnswerStatus.RESEARCH_REQUIRED,
        domain=EnergyDomain.NATURAL_GAS,
        direct_answer=(
            "The question was classified, but a live structured "
            "executor is not connected."
        ),
        simple_explanation="A controlled research path is available.",
        confidence="pending_research",
        limitations=("No structured executor is connected.",),
    )


def test_health_matches_public_version() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "CAISO Market Intelligence",
        "version": "4.0.0",
    }


def test_packaging_and_api_versions_match() -> None:
    metadata = tomllib.loads(
        Path("pyproject.toml").read_text(encoding="utf-8")
    )

    assert metadata["project"]["version"] == application.APP_VERSION
    assert application.app.version == application.APP_VERSION
    assert client.get("/api/status").json()["version"] == application.APP_VERSION


def test_search_respects_disabled_web_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        application,
        "_universal_orchestrator",
        FakeOrchestrator(research_required()),
    )

    response = client.post(
        "/api/search",
        json={
            "question": "Why did gas prices rise?",
            "allow_web_fallback": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "research_required"
    assert payload["used_web_fallback"] is False


def test_search_marks_controlled_web_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        application,
        "_universal_orchestrator",
        FakeOrchestrator(research_required()),
    )

    def fake_search(**_kwargs):
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Gas prices rose on tighter supply.",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://www.eia.gov/",
                                    "title": "U.S. EIA",
                                }
                            ],
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(application, "_search", fake_search)

    response = client.post(
        "/api/search",
        json={
            "question": "Why did gas prices rise?",
            "allow_web_fallback": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["used_web_fallback"] is True
    assert payload["confidence"] == "medium"
    assert payload["sources"][0]["primary"] is False


def test_structured_failure_does_not_expose_exception(
    monkeypatch,
    caplog,
) -> None:
    class BrokenOrchestrator:
        def answer(self, question: str):
            raise RuntimeError("private connector token=secret")

    monkeypatch.setattr(
        application,
        "_universal_orchestrator",
        BrokenOrchestrator(),
    )

    with caplog.at_level(logging.ERROR):
        response = client.post(
            "/api/search",
            json={"question": "What is CAISO demand?"},
        )

    assert response.status_code == 502
    body = response.text
    assert "secret" not in body
    assert "private connector" not in body
    assert "private connector token=secret" in caplog.text
