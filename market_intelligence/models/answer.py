from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from .evidence import EvidenceItem
from .query import MarketQuery


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResearchAnswer(BaseModel):
    answer: str
    simple_explanation: str
    query: MarketQuery
    evidence: list[EvidenceItem] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    searched_at: datetime
    source_count: int = 0
