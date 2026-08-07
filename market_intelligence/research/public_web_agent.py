from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from urllib.parse import urlparse

from market_intelligence.research.ddgs_provider import (
    DdgsSearchProvider,
)
from market_intelligence.research.page_fetcher import (
    PageFetcher,
    PageFetchError,
)
from market_intelligence.research.search_provider import (
    SearchProviderError,
)


LICENSED_DOMAINS = {
    "argusmedia.com",
    "bloomberg.com",
    "ice.com",
    "naturalgasintel.com",
    "ngi.com",
    "spglobal.com",
    "woodmac.com",
}

STOP_WORDS = {
    "about",
    "after",
    "ahead",
    "and",
    "are",
    "before",
    "did",
    "does",
    "for",
    "from",
    "have",
    "how",
    "into",
    "market",
    "price",
    "prices",
    "that",
    "the",
    "their",
    "this",
    "today",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
    "yesterday",
}


@dataclass(frozen=True)
class PublicWebSource:
    title: str
    url: str
    provider: str
    primary: bool
    excerpt: str
    retrieved_at: str | None


@dataclass(frozen=True)
class PublicWebAnswer:
    answer: str
    confidence: str
    sources: tuple[PublicWebSource, ...]
    limitations: tuple[str, ...]
    searched_at: str
    discovered_results: int
    retrieved_pages: int


def _hostname(url: str) -> str:
    value = (urlparse(url).hostname or "").lower().strip(".")
    return value.removeprefix("www.")


def _matches_domain(hostname: str, domain: str) -> bool:
    normalized = domain.lower().strip(".").removeprefix("www.")
    return hostname == normalized or hostname.endswith(f".{normalized}")


def _is_licensed(url: str) -> bool:
    hostname = _hostname(url)
    return any(_matches_domain(hostname, domain) for domain in LICENSED_DOMAINS)


def _is_allowed(url: str, allowed_domains: list[str] | None) -> bool:
    if _is_licensed(url):
        return False
    if not allowed_domains:
        return True
    hostname = _hostname(url)
    return any(_matches_domain(hostname, domain) for domain in allowed_domains)


def _keywords(question: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9-]{3,}", question.lower())
        if token not in STOP_WORDS
    }


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if 45 <= len(sentence.strip()) <= 420
    ]


def _best_excerpt(text: str, question: str) -> str:
    keywords = _keywords(question)
    candidates = _sentences(text)
    if not candidates:
        return re.sub(r"\s+", " ", text).strip()[:420]

    def score(sentence: str) -> tuple[int, int]:
        lowered = sentence.lower()
        matches = sum(1 for word in keywords if word in lowered)
        freshness = sum(
            1
            for word in ("current", "latest", "today", "2026", "hourly")
            if word in lowered
        )
        return matches * 5 + freshness, -len(sentence)

    return max(candidates, key=score)


class PublicWebResearchAgent:
    def __init__(
        self,
        *,
        search_provider: DdgsSearchProvider | None = None,
        fetcher: PageFetcher | None = None,
        maximum_results: int = 12,
        maximum_sources: int = 4,
    ) -> None:
        self.search_provider = search_provider or DdgsSearchProvider()
        self.fetcher = fetcher or PageFetcher()
        self.maximum_results = maximum_results
        self.maximum_sources = maximum_sources

    @staticmethod
    def _query(question: str, allowed_domains: list[str] | None) -> str:
        if not allowed_domains:
            return question
        site_filter = " OR ".join(
            f"site:{domain}" for domain in allowed_domains[:6]
        )
        return f"{question} ({site_filter})"

    def answer(
        self,
        question: str,
        *,
        allowed_domains: list[str] | None,
    ) -> PublicWebAnswer:
        normalized = question.strip()
        if not normalized:
            raise ValueError("Question cannot be blank.")

        limitations: list[str] = []
        query = self._query(normalized, allowed_domains)

        try:
            results = self.search_provider.search(
                query,
                max_results=self.maximum_results,
                timelimit=None,
            )
        except SearchProviderError as exc:
            limitations.append(str(exc))
            results = []

        approved = [
            result
            for result in results
            if _is_allowed(result.url, allowed_domains)
        ]

        if not approved and allowed_domains:
            try:
                broader = self.search_provider.search(
                    normalized,
                    max_results=self.maximum_results,
                    timelimit=None,
                )
            except SearchProviderError as exc:
                limitations.append(str(exc))
                broader = []
            approved = [
                result
                for result in broader
                if _is_allowed(result.url, allowed_domains)
            ]
            results.extend(broader)

        sources: list[PublicWebSource] = []
        seen_hosts: set[str] = set()

        for result in approved:
            if len(sources) >= self.maximum_sources:
                break
            host = _hostname(result.url)
            if not host or host in seen_hosts:
                continue

            try:
                page = self.fetcher.fetch(result.url)
                excerpt = _best_excerpt(page.text, normalized)
                title = page.title or result.title
                url = page.final_url
                retrieved_at = page.retrieved_at
            except PageFetchError as exc:
                if not result.snippet.strip():
                    limitations.append(f"{result.url}: {exc}")
                    continue
                excerpt = result.snippet.strip()
                title = result.title
                url = result.url
                retrieved_at = None
                limitations.append(
                    f"{result.url}: full page unavailable; search excerpt used."
                )

            sources.append(
                PublicWebSource(
                    title=title,
                    url=url,
                    provider=host,
                    primary=bool(
                        allowed_domains
                        and any(
                            _matches_domain(host, domain)
                            for domain in allowed_domains
                            if domain != "reuters.com"
                        )
                    ),
                    excerpt=excerpt,
                    retrieved_at=retrieved_at,
                )
            )
            seen_hosts.add(host)

        searched_at = datetime.now(timezone.utc).isoformat()
        if not sources:
            return PublicWebAnswer(
                answer=(
                    "I could not retrieve enough approved public evidence "
                    "to answer this question right now."
                ),
                confidence="insufficient",
                sources=(),
                limitations=tuple(dict.fromkeys(limitations)),
                searched_at=searched_at,
                discovered_results=len(results),
                retrieved_pages=0,
            )

        evidence_lines = [
            f"{source.excerpt} [{index}]"
            for index, source in enumerate(sources, start=1)
        ]
        answer = (
            "Current public-source research found:\n\n- "
            + "\n- ".join(evidence_lines)
        )

        return PublicWebAnswer(
            answer=answer,
            confidence="medium" if len(sources) >= 2 else "low",
            sources=tuple(sources),
            limitations=tuple(dict.fromkeys(limitations)),
            searched_at=searched_at,
            discovered_results=len(results),
            retrieved_pages=sum(
                1 for source in sources if source.retrieved_at is not None
            ),
        )
