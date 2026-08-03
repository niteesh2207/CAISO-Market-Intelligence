from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from market_intelligence.quality.models import (
    ClaimType,
    ReleaseDecision,
)


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class AnswerSource:
    source_id: str
    provider_id: str
    title: str
    url: str
    is_primary: bool
    authority_rank: int
    observed_at: datetime | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None


@dataclass(frozen=True)
class AnswerClaim:
    claim_id: str
    text: str
    claim_type: ClaimType
    source_ids: tuple[str, ...]
    value: float | int | str | None = None
    unit: str | None = None
    market: str | None = None
    timezone: str | None = None
    interval: str | None = None
    is_inference: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerPacket:
    question: str
    direct_answer: str
    simple_explanation: str
    claims: tuple[AnswerClaim, ...]
    sources: tuple[AnswerSource, ...]
    confidence: ConfidenceLevel
    release_decision: ReleaseDecision
    limitations: tuple[str, ...]
    generated_at: datetime

    @property
    def source_count(self) -> int:
        return len(self.sources)

    @property
    def primary_source_count(self) -> int:
        return sum(
            source.is_primary
            for source in self.sources
        )
