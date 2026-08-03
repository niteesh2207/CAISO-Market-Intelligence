from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from market_intelligence.connectors.catalog import (
    ProviderSpec,
)
from market_intelligence.retrieval.exceptions import (
    SourceRateLimitedError,
    SourceResponseError,
    SourceUnauthorizedError,
    SourceUnavailableError,
)
from market_intelligence.retrieval.models import (
    RetrievedRecord,
    RetrievalAttempt,
    RetrievalMethod,
    RetrievalOutcome,
    RetrievalStatus,
    utc_now,
)
from market_intelligence.retrieval.strategy import (
    build_provider_retrieval_plan,
)


Retriever = Callable[
    [ProviderSpec, RetrievalMethod, Any],
    list[RetrievedRecord],
]


def _status_for_exception(
    exc: Exception,
) -> RetrievalStatus:
    if isinstance(exc, SourceUnauthorizedError):
        return RetrievalStatus.UNAUTHORIZED

    if isinstance(exc, SourceRateLimitedError):
        return RetrievalStatus.RATE_LIMITED

    if isinstance(exc, SourceUnavailableError):
        return RetrievalStatus.UNAVAILABLE

    if isinstance(exc, SourceResponseError):
        return RetrievalStatus.INVALID_RESPONSE

    return RetrievalStatus.FAILED


class RetrievalOrchestrator:
    def __init__(
        self,
        retriever: Retriever,
    ) -> None:
        self.retriever = retriever

    def retrieve(
        self,
        *,
        providers: list[ProviderSpec],
        request: Any,
        credential_provider_ids: set[str] | None = None,
        licensed_provider_ids: set[str] | None = None,
        minimum_records: int = 1,
        require_primary: bool = True,
    ) -> RetrievalOutcome:
        credential_provider_ids = (
            credential_provider_ids or set()
        )
        licensed_provider_ids = (
            licensed_provider_ids or set()
        )

        attempts: list[RetrievalAttempt] = []
        records: list[RetrievedRecord] = []
        warnings: list[str] = []

        for provider in providers:
            plan = build_provider_retrieval_plan(
                provider,
                credentials_available=(
                    provider.provider_id
                    in credential_provider_ids
                ),
                licensed_access_available=(
                    provider.provider_id
                    in licensed_provider_ids
                ),
            )

            if plan.skip_reason:
                warnings.append(
                    f"{provider.name}: {plan.skip_reason}"
                )
                continue

            for method in plan.methods:
                started_at = utc_now()

                try:
                    returned = self.retriever(
                        provider,
                        method,
                        request,
                    )

                    records.extend(returned)

                    attempts.append(
                        RetrievalAttempt(
                            provider_id=provider.provider_id,
                            method=method,
                            status=RetrievalStatus.SUCCESS,
                            started_at=started_at,
                            finished_at=utc_now(),
                            metadata={
                                "record_count": len(returned),
                            },
                        )
                    )

                    has_primary = any(
                        record.is_primary
                        for record in records
                    )

                    if (
                        len(records) >= minimum_records
                        and (
                            not require_primary
                            or has_primary
                        )
                    ):
                        return RetrievalOutcome(
                            records=tuple(records),
                            attempts=tuple(attempts),
                            warnings=tuple(warnings),
                        )

                except Exception as exc:
                    attempts.append(
                        RetrievalAttempt(
                            provider_id=provider.provider_id,
                            method=method,
                            status=_status_for_exception(exc),
                            started_at=started_at,
                            finished_at=utc_now(),
                            error=(
                                f"{type(exc).__name__}: {exc}"
                            ),
                        )
                    )

                    continue

        if not records:
            warnings.append(
                "No accessible provider returned usable evidence."
            )
        elif (
            require_primary
            and not any(
                record.is_primary
                for record in records
            )
        ):
            warnings.append(
                "No primary-source record was available."
            )

        return RetrievalOutcome(
            records=tuple(records),
            attempts=tuple(attempts),
            warnings=tuple(warnings),
        )
