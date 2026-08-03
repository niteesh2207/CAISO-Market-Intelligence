from market_intelligence.connectors.catalog import (
    provider_by_id,
)
from market_intelligence.retrieval.models import (
    RetrievalMethod,
)
from market_intelligence.retrieval.strategy import (
    build_provider_retrieval_plan,
)


def test_eia_without_key_uses_bulk_then_official_web():
    provider = provider_by_id("eia_api")
    assert provider is not None

    plan = build_provider_retrieval_plan(
        provider,
        credentials_available=False,
    )

    assert (
        RetrievalMethod.STRUCTURED_API
        not in plan.methods
    )
    assert (
        RetrievalMethod.BULK_DOWNLOAD
        in plan.methods
    )
    assert (
        RetrievalMethod.OFFICIAL_WEB
        in plan.methods
    )


def test_eia_with_key_keeps_structured_api():
    provider = provider_by_id("eia_api")
    assert provider is not None

    plan = build_provider_retrieval_plan(
        provider,
        credentials_available=True,
    )

    assert (
        plan.methods[0]
        == RetrievalMethod.STRUCTURED_API
    )


def test_optional_licensed_provider_is_skipped():
    provider = provider_by_id(
        "woodmac_optional"
    )
    assert provider is not None

    plan = build_provider_retrieval_plan(
        provider,
        credentials_available=False,
        licensed_access_available=False,
    )

    assert plan.methods == ()
    assert plan.skip_reason is not None
