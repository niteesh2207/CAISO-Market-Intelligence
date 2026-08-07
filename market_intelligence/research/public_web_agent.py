from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import re
from urllib.parse import urlparse

from market_intelligence.research.ddgs_provider import (
    DdgsSearchProvider,
)
from market_intelligence.research.discovery_models import ProviderSearchResult
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
    "caiso",
    "current",
    "did",
    "does",
    "for",
    "from",
    "give",
    "have",
    "how",
    "into",
    "insights",
    "latest",
    "market",
    "now",
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
    published_at: str | None
    freshness: str
    authority: str


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


def _focused_terms(question: str) -> str:
    ordered: list[str] = []
    for token in re.findall(r"[a-z0-9-]{3,}", question.lower()):
        if token in STOP_WORDS or token in ordered:
            continue
        ordered.append(token)
    return " ".join(ordered)


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


def _keyword_overlap(text: str, question: str) -> int:
    lowered = text.lower()
    return sum(1 for word in _keywords(question) if word in lowered)


CURRENT_TERMS = {
    "current",
    "currently",
    "latest",
    "live",
    "now",
    "right now",
    "today",
    "this morning",
    "this afternoon",
    "this evening",
    "running",
    "operating",
}

LIVE_PATH_MARKERS = (
    "/todays-outlook/",
    "/today-s-outlook/",
    "/oasisapi/",
    "/outages/",
    "/current-conditions/",
)

BAD_RESULT_MARKERS = (
    "404",
    "access denied",
    "not found",
    "page not found",
)


def _requires_current_evidence(question: str) -> bool:
    lowered = question.lower()
    if any(term in lowered for term in CURRENT_TERMS):
        return True
    dynamic_terms = (
        "capacity",
        "congestion",
        "demand",
        "generation",
        "hydro",
        "outage",
        "price",
        "status",
    )
    historical_markers = (
        "historical",
        "in 20",
        "last year",
        "previous year",
    )
    return (
        any(term in lowered for term in dynamic_terms)
        and not any(term in lowered for term in historical_markers)
    )


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    lowered = cleaned.lower()
    now = datetime.now(timezone.utc)
    if "today" in lowered:
        return now
    if "yesterday" in lowered:
        return now - timedelta(days=1)
    relative = re.search(r"\b(\d+)\s+(hour|day|week)s?\s+ago\b", lowered)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        if unit == "hour":
            return now - timedelta(hours=amount)
        if unit == "day":
            return now - timedelta(days=amount)
        return now - timedelta(weeks=amount)
    longer_relative = re.search(
        r"\b(\d+(?:\.\d+)?)\s+(month|year)s?\s+ago\b",
        lowered,
    )
    if longer_relative:
        amount = float(longer_relative.group(1))
        days = amount * (30 if longer_relative.group(2) == "month" else 365)
        return now - timedelta(days=days)
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(cleaned)
        except (TypeError, ValueError):
            parsed = None
    if parsed is not None:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    match = re.search(
        r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b",
        cleaned,
    )
    if match:
        try:
            return datetime(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None
    named_date = re.search(
        r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),\s+(20\d{2})\b",
        cleaned,
        flags=re.IGNORECASE,
    )
    if named_date:
        try:
            return datetime.strptime(
                named_date.group(0),
                "%B %d, %Y",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                return datetime.strptime(
                    named_date.group(0),
                    "%b %d, %Y",
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                return None
    return None


def _result_date(result: object) -> datetime | None:
    published_at = getattr(result, "published_at", None)
    parsed = _parse_date(published_at)
    if parsed:
        return parsed
    searchable = " ".join(
        str(value)
        for value in (
            getattr(result, "title", ""),
            getattr(result, "url", ""),
            getattr(result, "snippet", ""),
        )
    )
    return _parse_date(searchable)


def _freshness_label(result: object, *, now: datetime) -> str:
    url = str(getattr(result, "url", "")).lower()
    if any(marker in url for marker in LIVE_PATH_MARKERS):
        return "live"
    published = _result_date(result)
    if published is None:
        return "unknown"
    age = now - published
    if age <= timedelta(days=2):
        return "current"
    if age <= timedelta(days=31):
        return "recent"
    return "historical"


def _authority_rank(url: str, allowed_domains: list[str] | None) -> int:
    host = _hostname(url)
    if not allowed_domains:
        return 100
    for index, domain in enumerate(allowed_domains):
        if _matches_domain(host, domain):
            return index
    return 100


def _result_score(
    result: object,
    question: str,
    *,
    allowed_domains: list[str] | None,
    now: datetime,
) -> tuple[int, int, int, int, int]:
    keywords = _keywords(question)
    combined = " ".join(
        str(value).lower()
        for value in (
            getattr(result, "title", ""),
            getattr(result, "snippet", ""),
            getattr(result, "url", ""),
        )
    )
    overlap = sum(1 for word in keywords if word in combined)
    freshness = _freshness_label(result, now=now)
    freshness_score = {
        "live": 40,
        "current": 35,
        "recent": 20,
        "unknown": 0,
        "historical": -25,
    }[freshness]
    authority = _authority_rank(
        str(getattr(result, "url", "")),
        allowed_domains,
    )
    host = _hostname(str(getattr(result, "url", "")))
    primary = bool(
        allowed_domains
        and any(
            _matches_domain(host, domain)
            for domain in allowed_domains
            if domain != "reuters.com"
        )
    )
    quality_score = freshness_score + (50 if primary else 0)
    published = _result_date(result)
    recency_score = int(published.timestamp()) if published else -1
    return (
        quality_score,
        recency_score,
        overlap * 10,
        -authority,
        -len(combined),
    )


def _is_relevant(result: object, question: str) -> bool:
    keywords = _keywords(question)
    combined = " ".join(
        str(value).lower()
        for value in (
            getattr(result, "title", ""),
            getattr(result, "snippet", ""),
            getattr(result, "url", ""),
        )
    )
    overlap = sum(1 for word in keywords if word in combined)
    required = 2 if len(keywords) >= 3 else 1
    return overlap >= required


def _is_bad_result(result: object) -> bool:
    title = str(getattr(result, "title", "")).lower()
    snippet = str(getattr(result, "snippet", "")).lower()
    return any(
        marker in title or marker in snippet
        for marker in BAD_RESULT_MARKERS
    )


def _official_live_candidates(
    question: str,
    allowed_domains: list[str] | None,
) -> list[ProviderSearchResult]:
    if not allowed_domains or not any(
        _matches_domain("caiso.com", domain)
        for domain in allowed_domains
    ):
        return []

    lowered = question.lower()
    pages: list[tuple[str, str, str]] = []
    if any(
        term in lowered
        for term in (
            "generation",
            "hydro",
            "renewable",
            "solar",
            "supply",
            "wind",
            "capacity",
        )
    ):
        pages.append((
            "Today's Outlook: Supply",
            "https://www.caiso.com/todays-outlook/supply",
            (
                "Current CAISO supply, generation, renewables, hydro, and "
                "resource-capacity context on five-minute averages."
            ),
        ))
    if any(term in lowered for term in ("demand", "load", "net load")):
        pages.append((
            "Today's Outlook: Demand",
            "https://www.caiso.com/todays-outlook/demand",
            "Current CAISO demand and net-demand operating information.",
        ))
    if any(
        term in lowered
        for term in ("price", "lmp", "np-15", "np15", "sp-15", "sp15")
    ):
        pages.append((
            "Today's Outlook: Prices",
            "https://www.caiso.com/todays-outlook/prices",
            "Current CAISO wholesale market-price information.",
        ))

    return [
        ProviderSearchResult(
            provider="official_live_registry",
            title=title,
            url=url,
            snippet=snippet,
            source_engine="official_live_registry",
            query=question,
            metadata={"live_endpoint": True},
        )
        for title, url, snippet in pages
    ]


def _discovered_count(results: list[ProviderSearchResult]) -> int:
    return sum(
        1
        for result in results
        if result.provider != "official_live_registry"
    )


def _compose_answer(
    question: str,
    sources: list[PublicWebSource],
) -> str:
    lowered = question.lower()
    if (
        "hydro" in lowered
        and any(term in lowered for term in ("capacity", "maximum", "max"))
        and any(
            source.url == "https://www.caiso.com/todays-outlook/supply"
            for source in sources
        )
    ):
        return (
            "CAISO's latest public Supply page does not identify individual "
            "hydroelectric facilities operating at maximum or nameplate "
            "capacity. It reports generation by resource type on a "
            "five-minute average, so no specific hydro plant can be verified "
            "as running at maximum capacity from the current public evidence "
            "[1]."
        )

    evidence_lines = [
        f"{source.excerpt} [{index}]"
        for index, source in enumerate(sources, start=1)
    ]
    return (
        "Current public-source research found:\n\n- "
        + "\n- ".join(evidence_lines)
    )


class PublicWebResearchAgent:
    def __init__(
        self,
        *,
        search_provider: DdgsSearchProvider | None = None,
        fetcher: PageFetcher | None = None,
        maximum_results: int = 20,
        maximum_sources: int = 4,
    ) -> None:
        self.search_provider = search_provider or DdgsSearchProvider()
        self.fetcher = fetcher or PageFetcher()
        self.maximum_results = maximum_results
        self.maximum_sources = maximum_sources

    @staticmethod
    def _query(question: str, allowed_domains: list[str] | None) -> str:
        current_year = datetime.now(timezone.utc).year
        focused = _focused_terms(question) or question
        freshness = (
            f" {current_year}"
            if _requires_current_evidence(question)
            else ""
        )
        if not allowed_domains:
            return f"{focused}{freshness}"
        primary_authority = allowed_domains[0]
        authority_names = {
            "caiso.com": "CAISO",
            "eia.gov": "EIA",
            "ferc.gov": "FERC",
            "nrc.gov": "NRC",
            "noaa.gov": "NOAA",
        }
        authority = authority_names.get(primary_authority, primary_authority)
        return f"{focused} {authority}{freshness}"

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
        now = datetime.now(timezone.utc)
        current_required = _requires_current_evidence(normalized)
        timelimit = None if current_required else "y"

        try:
            results = self.search_provider.search(
                query,
                max_results=self.maximum_results,
                timelimit=timelimit,
            )
        except SearchProviderError as exc:
            limitations.append(str(exc))
            results = []

        results = [
            *_official_live_candidates(normalized, allowed_domains),
            *results,
        ]

        approved = [
            result
            for result in results
            if _is_allowed(result.url, allowed_domains)
            and not _is_bad_result(result)
            and (
                result.provider == "official_live_registry"
                or _is_relevant(result, normalized)
            )
        ]

        if not approved and allowed_domains:
            try:
                broader = self.search_provider.search(
                    f"{_focused_terms(normalized)} CAISO {now.year}",
                    max_results=self.maximum_results,
                    timelimit=None,
                )
            except SearchProviderError as exc:
                limitations.append(str(exc))
                broader = []
            approved.extend(
                result
                for result in broader
                if _is_allowed(result.url, allowed_domains)
                and not _is_bad_result(result)
                and _is_relevant(result, normalized)
            )
            results.extend(broader)

        deduplicated: dict[str, ProviderSearchResult] = {}
        for result in approved:
            deduplicated.setdefault(result.url, result)
        approved = list(deduplicated.values())

        approved = sorted(
            approved,
            key=lambda result: _result_score(
                result,
                normalized,
                allowed_domains=allowed_domains,
                now=now,
            ),
            reverse=True,
        )

        sources: list[PublicWebSource] = []
        seen_urls: set[str] = set()
        host_counts: dict[str, int] = {}

        for result in approved:
            if len(sources) >= self.maximum_sources:
                break
            host = _hostname(result.url)
            if (
                not host
                or result.url in seen_urls
                or host_counts.get(host, 0) >= 2
            ):
                continue

            freshness = _freshness_label(result, now=now)

            try:
                page = self.fetcher.fetch(result.url)
                page_excerpt = _best_excerpt(page.text, normalized)
                search_excerpt = result.snippet.strip()
                excerpt = (
                    search_excerpt
                    if search_excerpt
                    and _keyword_overlap(search_excerpt, normalized)
                    > _keyword_overlap(page_excerpt, normalized)
                    else page_excerpt
                )
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
                    published_at=result.published_at,
                    freshness=freshness,
                    authority=(
                        "primary"
                        if allowed_domains
                        and any(
                            _matches_domain(host, domain)
                            for domain in allowed_domains
                            if domain != "reuters.com"
                        )
                        else "supporting"
                    ),
                )
            )
            seen_urls.add(result.url)
            host_counts[host] = host_counts.get(host, 0) + 1

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
                discovered_results=_discovered_count(results),
                retrieved_pages=0,
            )

        if current_required and not any(
            source.primary
            and source.freshness in {"live", "current", "recent"}
            and source.retrieved_at is not None
            for source in sources
        ):
            limitations.append(
                "No recent, successfully retrieved primary source was "
                "available; a current factual claim was withheld."
            )
            latest_reference = next(
                (
                    (index, source)
                    for index, source in enumerate(sources, start=1)
                    if source.published_at is not None
                ),
                (None, None),
            )
            latest_index, latest_source = latest_reference
            dated_context = (
                f" The newest dated source found was published "
                f"{latest_source.published_at} [{latest_index}]; it is shown only as "
                "historical context."
                if latest_source is not None
                else " The available sources did not expose a publication date."
            )
            return PublicWebAnswer(
                answer=(
                    "I could not verify a current answer from recent "
                    "primary public evidence. The sources found were stale, "
                    "undated, or unavailable, so I am not treating them as "
                    "a reliable statement of present CAISO conditions."
                    + dated_context
                ),
                confidence="insufficient",
                sources=tuple(sources),
                limitations=tuple(dict.fromkeys(limitations)),
                searched_at=searched_at,
                discovered_results=_discovered_count(results),
                retrieved_pages=sum(
                    1 for source in sources if source.retrieved_at is not None
                ),
            )

        answer = _compose_answer(normalized, sources)

        return PublicWebAnswer(
            answer=answer,
            confidence="medium" if len(sources) >= 2 else "low",
            sources=tuple(sources),
            limitations=tuple(dict.fromkeys(limitations)),
            searched_at=searched_at,
            discovered_results=_discovered_count(results),
            retrieved_pages=sum(
                1 for source in sources if source.retrieved_at is not None
            ),
        )
