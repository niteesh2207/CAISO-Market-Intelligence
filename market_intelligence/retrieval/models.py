from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class RetrievalStatus(StrEnum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    INVALID_RESPONSE = "invalid_response"
    FAILED = "failed"


class RetrievalMethod(StrEnum):
    STRUCTURED_API = "structured_api"
    BULK_DOWNLOAD = "bulk_download"
    OFFICIAL_WEB = "official_web"
    DOCUMENT_SEARCH = "document_search"
    REPUTABLE_WEB = "reputable_web"


@dataclass(frozen=True)
class RetrievalAttempt:
    provider_id: str
    method: RetrievalMethod
    status: RetrievalStatus
    started_at: datetime
    finished_at: datetime
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedRecord:
    provider_id: str
    method: RetrievalMethod
    source_title: str
    source_url: str
    observed_at: datetime | None
    published_at: datetime | None
    retrieved_at: datetime
    payload: Any
    is_primary: bool
    authority_rank: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalOutcome:
    records: tuple[RetrievedRecord, ...]
    attempts: tuple[RetrievalAttempt, ...]
    warnings: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return bool(self.records)

    @property
    def primary_record_count(self) -> int:
        return sum(
            record.is_primary
            for record in self.records
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
