from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from market_intelligence.quality.models import (
    EvidenceQualityInput,
)
from market_intelligence.retrieval.models import (
    RetrievedRecord,
    RetrievalOutcome,
)


def _source_identity(
    record: RetrievedRecord,
) -> str:
    identity = record.metadata.get(
        "independent_source_id"
    )

    if identity:
        return str(identity)

    return record.provider_id


def quality_input_from_retrieval(
    outcome: RetrievalOutcome,
    *,
    evaluated_at: datetime | None = None,
    complete_coverage: bool | None = None,
    has_unit: bool | None = None,
    has_market_context: bool | None = None,
    has_timezone: bool | None = None,
    calculation_verified: bool = True,
    has_source_conflict: bool = False,
) -> EvidenceQualityInput:
    records = list(outcome.records)

    observed_times = [
        record.observed_at
        for record in records
        if record.observed_at is not None
    ]

    independent_sources = {
        _source_identity(record)
        for record in records
    }

    def metadata_flag(
        key: str,
        explicit_value: bool | None,
        default: bool,
    ) -> bool:
        if explicit_value is not None:
            return explicit_value

        values = [
            record.metadata.get(key)
            for record in records
            if key in record.metadata
        ]

        if not values:
            return default

        return all(bool(value) for value in values)

    return EvidenceQualityInput(
        record_count=len(records),
        primary_record_count=sum(
            record.is_primary
            for record in records
        ),
        independent_source_count=len(
            independent_sources
        ),
        newest_observed_at=(
            max(observed_times)
            if observed_times
            else None
        ),
        oldest_observed_at=(
            min(observed_times)
            if observed_times
            else None
        ),
        evaluated_at=(
            evaluated_at
            or datetime.now(timezone.utc)
        ),
        has_source_conflict=has_source_conflict,
        complete_coverage=metadata_flag(
            "complete_coverage",
            complete_coverage,
            True,
        ),
        has_unit=metadata_flag(
            "has_unit",
            has_unit,
            True,
        ),
        has_market_context=metadata_flag(
            "has_market_context",
            has_market_context,
            True,
        ),
        has_timezone=metadata_flag(
            "has_timezone",
            has_timezone,
            True,
        ),
        calculation_verified=calculation_verified,
        metadata={
            "retrieval_warnings": outcome.warnings,
            "attempt_count": len(outcome.attempts),
        },
    )
