from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from market_intelligence.research.discovery_models import (
    ProviderSearchResult,
)
from market_intelligence.research.search_provider import (
    SearchProviderError,
)


SearchFunction = Callable[..., list[dict[str, Any]]]


def default_text_search(
    query: str,
    *,
    region: str,
    safesearch: str,
    timelimit: str | None,
    max_results: int,
    backend: str,
) -> list[dict[str, Any]]:
    from ddgs import DDGS

    return DDGS(
        timeout=20,
    ).text(
        query,
        region=region,
        safesearch=safesearch,
        timelimit=timelimit,
        max_results=max_results,
        backend=backend,
    )


@dataclass(frozen=True)
class DdgsSearchProvider:
    provider_name: str = "ddgs_web"
    region: str = "us-en"
    safesearch: str = "moderate"
    backend: str = "yahoo,brave,bing"
    search_function: SearchFunction = (
        default_text_search
    )

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        timelimit: str | None = None,
    ) -> list[ProviderSearchResult]:
        cleaned = query.strip()

        if not cleaned:
            raise ValueError(
                "Search query cannot be blank."
            )

        if not 1 <= max_results <= 50:
            raise ValueError(
                "max_results must be between "
                "1 and 50."
            )

        try:
            raw_results = self.search_function(
                cleaned,
                region=self.region,
                safesearch=self.safesearch,
                timelimit=timelimit,
                max_results=max_results,
                backend=self.backend,
            )
        except Exception as exc:
            raise SearchProviderError(
                f"DDGS search failed: {exc}"
            ) from exc

        normalized: list[
            ProviderSearchResult
        ] = []

        seen_urls: set[str] = set()

        for item in raw_results or []:
            title = str(
                item.get("title", "")
            ).strip()

            url = str(
                item.get(
                    "href",
                    item.get("url", ""),
                )
            ).strip()

            snippet = str(
                item.get(
                    "body",
                    item.get(
                        "description",
                        "",
                    ),
                )
            ).strip()

            if not title or not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            normalized.append(
                ProviderSearchResult(
                    provider=self.provider_name,
                    title=title,
                    url=url,
                    snippet=snippet,
                    published_at=(
                        str(
                            item.get(
                                "date",
                                "",
                            )
                        ).strip()
                        or None
                    ),
                    source_engine=(
                        str(
                            item.get(
                                "source",
                                "",
                            )
                        ).strip()
                        or None
                    ),
                    query=cleaned,
                    metadata={
                        "backend": self.backend,
                    },
                )
            )

        return normalized
