from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceTier(str, Enum):
    CONTROLLING = "controlling"
    AUTHORITATIVE = "authoritative"
    SUPPORTING = "supporting"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    domain: str = ""
    published_at: str | None = None
    source_tier: SourceTier = SourceTier.UNKNOWN
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchSource:
    provider: str
    title: str
    url: str
    excerpt: str
    primary: bool
    source_tier: SourceTier
    published_at: str | None = None
    retrieved_at: str | None = None


@dataclass(frozen=True)
class ResearchAnswer:
    status: str
    answer: str
    explanation: str
    confidence: str
    as_of: str
    sources: tuple[ResearchSource, ...] = ()
    limitations: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)
