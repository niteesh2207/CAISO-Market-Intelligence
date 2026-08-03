from datetime import datetime, timezone

from market_intelligence.connectors.catalog import (
    provider_by_id,
)
from market_intelligence.retrieval.exceptions import (
    SourceUnauthorizedError,
)
from market_intelligence.retrieval.models import (
    RetrievedRecord,
    RetrievalMethod,
    RetrievalStatus,
)
from market_intelligence.retrieval.orchestrator import (
    RetrievalOrchestrator,
)


def record(
    *,
    provider_id: str,
    method: RetrievalMethod,
    is_primary: bool,
) -> RetrievedRecord:
    return RetrievedRecord(
        provider_id=provider_id,
        method=method,
        source_title="Test source",
        source_url="https://example.com",
        observed_at=None,
        published_at=None,
        retrieved_at=datetime.now(timezone.utc),
        payload={"value": 1},
        is_primary=is_primary,
        authority_rank=1,
    )


def test_api_failure_falls_back_to_bulk():
    provider = provider_by_id("eia_api")
    assert provider is not None

    calls = []

    def retriever(provider, method, request):
        calls.append(method)

        if method == RetrievalMethod.STRUCTURED_API:
            raise SourceUnauthorizedError(
                "Invalid API key"
            )

        if method == RetrievalMethod.BULK_DOWNLOAD:
            return [
                record(
                    provider_id=provider.provider_id,
                    method=method,
                    is_primary=True,
                )
            ]

        return []

    outcome = RetrievalOrchestrator(
        retriever
    ).retrieve(
        providers=[provider],
        request={"query": "gas storage"},
        credential_provider_ids={"eia_api"},
    )

    assert outcome.succeeded is True
    assert calls == [
        RetrievalMethod.STRUCTURED_API,
        RetrievalMethod.BULK_DOWNLOAD,
    ]
    assert outcome.attempts[0].status == (
        RetrievalStatus.UNAUTHORIZED
    )
    assert outcome.attempts[1].status == (
        RetrievalStatus.SUCCESS
    )


def test_no_key_skips_api_and_uses_bulk():
    provider = provider_by_id("eia_api")
    assert provider is not None

    calls = []

    def retriever(provider, method, request):
        calls.append(method)

        if method == RetrievalMethod.BULK_DOWNLOAD:
            return [
                record(
                    provider_id=provider.provider_id,
                    method=method,
                    is_primary=True,
                )
            ]

        return []

    outcome = RetrievalOrchestrator(
        retriever
    ).retrieve(
        providers=[provider],
        request={},
        credential_provider_ids=set(),
    )

    assert outcome.succeeded is True
    assert calls[0] == RetrievalMethod.BULK_DOWNLOAD
    assert (
        RetrievalMethod.STRUCTURED_API
        not in calls
    )


def test_primary_source_is_required_by_default():
    provider = provider_by_id("reuters")
    assert provider is not None

    def retriever(provider, method, request):
        return [
            record(
                provider_id=provider.provider_id,
                method=method,
                is_primary=False,
            )
        ]

    outcome = RetrievalOrchestrator(
        retriever
    ).retrieve(
        providers=[provider],
        request={},
    )

    assert outcome.succeeded is True
    assert (
        "No primary-source record was available."
        in outcome.warnings
    )
