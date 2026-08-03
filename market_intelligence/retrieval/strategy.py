from __future__ import annotations

from dataclasses import dataclass

from market_intelligence.connectors.catalog import (
    ConnectorKind,
    ProviderAccess,
    ProviderSpec,
)
from market_intelligence.retrieval.models import (
    RetrievalMethod,
)


@dataclass(frozen=True)
class ProviderRetrievalPlan:
    provider_id: str
    methods: tuple[RetrievalMethod, ...]
    skip_reason: str | None = None


KIND_TO_METHOD = {
    ConnectorKind.STRUCTURED_API:
        RetrievalMethod.STRUCTURED_API,
    ConnectorKind.STRUCTURED_DOWNLOAD:
        RetrievalMethod.BULK_DOWNLOAD,
    ConnectorKind.DOCUMENT_SEARCH:
        RetrievalMethod.DOCUMENT_SEARCH,
    ConnectorKind.WEB_RESEARCH:
        RetrievalMethod.OFFICIAL_WEB,
    ConnectorKind.FILE_IMPORT:
        RetrievalMethod.BULK_DOWNLOAD,
}


def build_provider_retrieval_plan(
    provider: ProviderSpec,
    *,
    credentials_available: bool,
    licensed_access_available: bool = False,
) -> ProviderRetrievalPlan:
    if (
        provider.access == ProviderAccess.OPTIONAL_LICENSED
        and not licensed_access_available
    ):
        return ProviderRetrievalPlan(
            provider_id=provider.provider_id,
            methods=(),
            skip_reason=(
                "Licensed access is not configured."
            ),
        )

    methods: list[RetrievalMethod] = []

    for connector_kind in provider.connector_kinds:
        method = KIND_TO_METHOD[connector_kind]

        if (
            method == RetrievalMethod.STRUCTURED_API
            and provider.access
            == ProviderAccess.PUBLIC_API_KEY
            and not credentials_available
        ):
            continue

        if method not in methods:
            methods.append(method)

    # Every primary provider may use official web retrieval as
    # a fallback when its API or bulk endpoint is unavailable.
    if (
        provider.is_primary
        and RetrievalMethod.OFFICIAL_WEB not in methods
    ):
        methods.append(
            RetrievalMethod.OFFICIAL_WEB
        )

    return ProviderRetrievalPlan(
        provider_id=provider.provider_id,
        methods=tuple(methods),
    )
