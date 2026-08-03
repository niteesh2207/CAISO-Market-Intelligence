from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class EvidenceKind(StrEnum):
    FACT = "fact"
    CALCULATION = "calculation"
    INFERENCE = "inference"
    MARKET_INTERPRETATION = "market_interpretation"


class SourceTier(StrEnum):
    PRIMARY = "primary"
    REPUTABLE_SECONDARY = "reputable_secondary"
    DISCOVERY = "discovery"


class EvidenceItem(BaseModel):
    claim: str = Field(min_length=1)
    kind: EvidenceKind
    source_title: str = Field(min_length=1)
    source_url: HttpUrl
    source_tier: SourceTier
    publisher: str | None = None
    published_at: datetime | None = None
    observed_at: datetime | None = None
    retrieved_at: datetime
    market_timezone: str | None = None
    unit: str | None = None
    value: float | str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
