from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResearchPlan:
    question: str
    is_energy_related: bool
    domain: str
    intent: str
    geography: tuple[str, ...]
    entities: tuple[str, ...]
    freshness: str
    search_queries: tuple[str, ...]
    official_domains: tuple[str, ...]
    reasoning_summary: str
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class ProviderSearchResult:
    provider: str
    title: str
    url: str
    snippet: str
    published_at: str | None = None
    source_engine: str | None = None
    query: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
