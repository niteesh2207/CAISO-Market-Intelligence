from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from market_intelligence.research.gdelt_client import (
    GdeltClient,
    GdeltError,
)
from market_intelligence.research.models import (
    ResearchAnswer,
    ResearchSource,
    SearchResult,
    SourceTier,
)
from market_intelligence.research.ollama_client import (
    OllamaClient,
    OllamaError,
)
from market_intelligence.research.page_fetcher import (
    PageFetcher,
    PageFetchError,
)
from market_intelligence.research.source_ranker import (
    rank_results,
)


@dataclass
class FreeResearchAgent:
    gdelt: GdeltClient
    fetcher: PageFetcher
    ollama: OllamaClient
    maximum_candidates: int = 8
    maximum_sources: int = 4
    maximum_excerpt_characters: int = 5_000

    def _discover(
        self,
        question: str,
    ) -> tuple[list[SearchResult], list[str]]:
        limitations: list[str] = []

        try:
            results = self.gdelt.search(
                question,
                max_records=12,
                timespan="7days",
            )
        except GdeltError as exc:
            limitations.append(str(exc))
            results = []

        return (
            rank_results(
                results,
                question,
            ),
            limitations,
        )

    def _collect_sources(
        self,
        results: list[SearchResult],
    ) -> tuple[list[ResearchSource], list[str]]:
        sources: list[ResearchSource] = []
        limitations: list[str] = []
        seen_domains: set[str] = set()

        for result in results[
            : self.maximum_candidates
        ]:
            if len(sources) >= self.maximum_sources:
                break

            domain = (
                result.domain
                or (
                    urlparse(
                        result.url
                    ).hostname
                    or ""
                )
            ).lower()

            # Avoid filling the answer with repeated
            # articles from a single publisher.
            if domain and domain in seen_domains:
                continue

            try:
                page = self.fetcher.fetch(
                    result.url
                )
            except PageFetchError as exc:
                limitations.append(
                    f"{result.url}: {exc}"
                )
                continue

            provider = (
                urlparse(
                    page.final_url
                ).hostname
                or domain
                or "unknown"
            )

            excerpt = page.text[
                : self.maximum_excerpt_characters
            ]

            sources.append(
                ResearchSource(
                    provider=provider,
                    title=(
                        page.title
                        or result.title
                    ),
                    url=page.final_url,
                    excerpt=excerpt,
                    primary=(
                        result.source_tier
                        == SourceTier.CONTROLLING
                    ),
                    source_tier=(
                        result.source_tier
                    ),
                    published_at=(
                        result.published_at
                    ),
                    retrieved_at=(
                        page.retrieved_at
                    ),
                )
            )

            if domain:
                seen_domains.add(domain)

        return sources, limitations

    @staticmethod
    def _evidence_text(
        sources: list[ResearchSource],
    ) -> str:
        blocks: list[str] = []

        for index, source in enumerate(
            sources,
            start=1,
        ):
            blocks.append(
                "\n".join(
                    (
                        f"SOURCE {index}",
                        f"TITLE: {source.title}",
                        f"PROVIDER: {source.provider}",
                        f"URL: {source.url}",
                        (
                            "SOURCE_TIER: "
                            + source.source_tier.value
                        ),
                        (
                            "PUBLISHED_AT: "
                            + str(
                                source.published_at
                                or "unknown"
                            )
                        ),
                        "EXCERPT:",
                        source.excerpt,
                    )
                )
            )

        return "\n\n".join(blocks)

    def answer(
        self,
        question: str,
    ) -> ResearchAnswer:
        normalized = question.strip()

        if not normalized:
            raise ValueError(
                "Question cannot be blank."
            )

        results, limitations = self._discover(
            normalized
        )

        sources, fetch_limitations = (
            self._collect_sources(results)
        )

        limitations.extend(
            fetch_limitations
        )

        if not sources:
            return ResearchAnswer(
                status="research_unavailable",
                answer=(
                    "I could not retrieve enough "
                    "verifiable source material to "
                    "answer this question."
                ),
                explanation=(
                    "The research providers returned "
                    "no usable source pages."
                ),
                confidence="insufficient",
                as_of=datetime.now(
                    timezone.utc
                ).isoformat(),
                sources=(),
                limitations=tuple(
                    limitations
                ),
                evidence={
                    "discovered_results": len(
                        results
                    ),
                    "retrieved_sources": 0,
                },
            )

        try:
            synthesis = (
                self.ollama.structured_answer(
                    question=normalized,
                    evidence_text=self._evidence_text(
                        sources
                    ),
                )
            )
        except OllamaError as exc:
            limitations.append(str(exc))

            return ResearchAnswer(
                status="research_unavailable",
                answer=(
                    "The evidence was retrieved, "
                    "but the local synthesis model "
                    "could not complete the answer."
                ),
                explanation=(
                    "Source retrieval succeeded, "
                    "but evidence synthesis failed."
                ),
                confidence="insufficient",
                as_of=datetime.now(
                    timezone.utc
                ).isoformat(),
                sources=tuple(sources),
                limitations=tuple(
                    limitations
                ),
                evidence={
                    "discovered_results": len(
                        results
                    ),
                    "retrieved_sources": len(
                        sources
                    ),
                },
            )

        limitations.extend(
            synthesis.get(
                "limitations",
                [],
            )
        )

        return ResearchAnswer(
            status="answered",
            answer=synthesis["answer"],
            explanation=(
                synthesis["explanation"]
            ),
            confidence=(
                synthesis["confidence"]
            ),
            as_of=datetime.now(
                timezone.utc
            ).isoformat(),
            sources=tuple(sources),
            limitations=tuple(
                dict.fromkeys(limitations)
            ),
            evidence={
                "discovered_results": len(
                    results
                ),
                "retrieved_sources": len(
                    sources
                ),
            },
        )
