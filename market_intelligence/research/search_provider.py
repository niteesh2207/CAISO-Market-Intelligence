from __future__ import annotations

from typing import Protocol

from market_intelligence.research.discovery_models import (
    ProviderSearchResult,
)


class SearchProviderError(RuntimeError):
    pass


class SearchProvider(Protocol):
    provider_name: str

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        timelimit: str | None = None,
    ) -> list[ProviderSearchResult]:
        ...
