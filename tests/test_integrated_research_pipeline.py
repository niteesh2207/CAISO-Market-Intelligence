from datetime import datetime, timezone

from market_intelligence.quality.models import (
    ClaimType,
    ReleaseDecision,
)
from market_intelligence.retrieval.exceptions import (
    SourceUnauthorizedError,
)
from market_intelligence.retrieval.models import (
    RetrievedRecord,
    RetrievalMethod,
)
from market_intelligence.service.models import (
    ResearchRequest,
    ResearchStatus,
)
from market_intelligence.service.pipeline import (
    EnergyResearchService,
)


NOW = datetime.now(timezone.utc)


def official_record(
    *,
    provider_id: str,
    method: RetrievalMethod,
    payload: dict,
) -> RetrievedRecord:
    return RetrievedRecord(
        provider_id=provider_id,
        method=method,
        source_title="Official source",
        source_url="https://example.com/official",
        observed_at=NOW,
        published_at=NOW,
        retrieved_at=NOW,
        payload=payload,
        is_primary=True,
        authority_rank=1,
        metadata={
            "complete_coverage": True,
            "has_unit": True,
            "has_market_context": True,
            "has_timezone": True,
        },
    )


def test_np15_numeric_question_runs_end_to_end():
    def retriever(provider, method, request):
        if provider.provider_id != "caiso_oasis":
            return []

        return [
            official_record(
                provider_id="caiso_oasis",
                method=method,
                payload={
                    "direct_answer": (
                        "The verified settlement price "
                        "was $45/MWh."
                    ),
                    "simple_explanation": (
                        "The official market result reports "
                        "$45 per megawatt-hour."
                    ),
                    "value": 45.0,
                    "unit": "USD/MWh",
                    "market": "CAISO day-ahead NP-15",
                    "timezone": "America/Los_Angeles",
                    "interval": "hourly",
                },
            )
        ]

    service = EnergyResearchService(
        retriever=retriever
    )

    result = service.research(
        ResearchRequest(
            question=(
                "What prices did NP-15 settle for yesterday?"
            ),
            claim_type=ClaimType.NUMERIC_FACT,
            context={
                "has_unit": True,
                "has_market_context": True,
                "has_timezone": True,
                "complete_coverage": True,
            },
        )
    )

    assert result.status == ResearchStatus.ANSWERED
    assert result.answer.confidence.value == "high"
    assert result.answer.primary_source_count == 1
    assert result.answer.claims[0].unit == "USD/MWh"
    assert (
        result.trace.classification.commodity.value
        == "electricity"
    )


def test_failed_api_falls_back_and_answers():
    calls = []

    def retriever(provider, method, request):
        if provider.provider_id != "eia_api":
            return []

        calls.append(method)

        if method == RetrievalMethod.STRUCTURED_API:
            raise SourceUnauthorizedError(
                "API access rejected"
            )

        if method == RetrievalMethod.BULK_DOWNLOAD:
            return [
                official_record(
                    provider_id="eia_api",
                    method=method,
                    payload={
                        "direct_answer": (
                            "Natural-gas storage increased."
                        ),
                        "simple_explanation": (
                            "The official bulk dataset reports "
                            "a net storage injection."
                        ),
                    },
                )
            ]

        return []

    service = EnergyResearchService(
        retriever=retriever
    )

    result = service.research(
        ResearchRequest(
            question=(
                "Did U.S. natural gas storage increase?"
            ),
            claim_type=ClaimType.OBSERVED_FACT,
            credential_provider_ids=frozenset(
                {"eia_api"}
            ),
        )
    )

    assert result.status == ResearchStatus.ANSWERED
    assert calls == [
        RetrievalMethod.STRUCTURED_API,
        RetrievalMethod.BULK_DOWNLOAD,
    ]


def test_missing_numeric_unit_is_held():
    def retriever(provider, method, request):
        return [
            official_record(
                provider_id=provider.provider_id,
                method=method,
                payload={
                    "direct_answer": "The value was 45.",
                    "simple_explanation": (
                        "A numerical value was retrieved, "
                        "but its unit was not verified."
                    ),
                    "value": 45,
                    "market": "Test market",
                    "timezone": "UTC",
                },
            )
        ]

    service = EnergyResearchService(
        retriever=retriever
    )

    result = service.research(
        ResearchRequest(
            question="What was the market value?",
            claim_type=ClaimType.NUMERIC_FACT,
            context={
                "has_unit": False,
                "has_market_context": True,
                "has_timezone": True,
            },
        )
    )

    assert result.status == ResearchStatus.HELD
    assert (
        result.answer.release_decision
        == ReleaseDecision.REFUSE_NUMERIC_CLAIM
    )
    assert result.answer.confidence.value == "insufficient"


def test_no_evidence_returns_controlled_hold():
    service = EnergyResearchService(
        retriever=lambda provider, method, request: []
    )

    result = service.research(
        ResearchRequest(
            question=(
                "Is an unidentified power plant online?"
            ),
            claim_type=ClaimType.OBSERVED_FACT,
        )
    )

    assert result.status == ResearchStatus.HELD
    assert result.answer.limitations
    assert result.answer.source_count == 0


def test_question_selects_expected_provider():
    seen = []

    def retriever(provider, method, request):
        seen.append(provider.provider_id)

        if provider.provider_id == "nrc_reactor_status":
            return [
                official_record(
                    provider_id=provider.provider_id,
                    method=method,
                    payload={
                        "direct_answer": (
                            "The reactor status was verified."
                        ),
                        "simple_explanation": (
                            "The official reactor-status source "
                            "was used."
                        ),
                    },
                )
            ]

        return []

    service = EnergyResearchService(
        retriever=retriever
    )

    result = service.research(
        ResearchRequest(
            question=(
                "Is Diablo Canyon running at full capacity?"
            ),
            claim_type=ClaimType.OBSERVED_FACT,
        )
    )

    assert result.status == ResearchStatus.ANSWERED
    assert seen[0] == "nrc_reactor_status"


def test_empty_question_is_rejected():
    service = EnergyResearchService(
        retriever=lambda provider, method, request: []
    )

    try:
        service.research(
            ResearchRequest(
                question=" ",
                claim_type=ClaimType.OBSERVED_FACT,
            )
        )
    except ValueError as exc:
        assert "cannot be empty" in str(exc)
    else:
        raise AssertionError(
            "Empty question was not rejected."
        )
