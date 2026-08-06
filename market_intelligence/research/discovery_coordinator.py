from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)

from market_intelligence.research.authority_registry import (
    authority_for_url,
)
from market_intelligence.research.discovery_models import (
    ProviderSearchResult,
    ResearchPlan,
)
from market_intelligence.research.search_provider import (
    SearchProvider,
    SearchProviderError,
)


STOPWORDS = {
    "about",
    "after",
    "also",
    "are",
    "been",
    "before",
    "being",
    "can",
    "could",
    "data",
    "does",
    "for",
    "from",
    "have",
    "how",
    "into",
    "latest",
    "most",
    "new",
    "that",
    "the",
    "their",
    "there",
    "these",
    "this",
    "today",
    "what",
    "when",
    "where",
    "which",
    "will",
    "with",
    "would",
}


TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


LOW_VALUE_PATTERNS = (
    r"\blogin\b",
    r"\bregister\b",
    r"\bsign in\b",
    r"\baccount portal\b",
    r"\bprivacy policy\b",
    r"\bterms of use\b",
    r"\bcontact us\b",
)


@dataclass(frozen=True)
class DiscoveryFailure:
    provider: str
    query: str
    error: str


@dataclass(frozen=True)
class DiscoveryCandidate:
    result: ProviderSearchResult
    score: float
    matched_terms: tuple[str, ...]
    official_domain: bool
    duplicate_queries: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryReport:
    plan: ResearchPlan
    candidates: tuple[DiscoveryCandidate, ...]
    failures: tuple[DiscoveryFailure, ...]
    raw_result_count: int
    deduplicated_result_count: int
    provider_counts: dict[str, int] = field(
        default_factory=dict
    )


def canonicalize_url(
    url: str,
) -> str:
    parsed = urlsplit(url.strip())

    scheme = parsed.scheme.lower()
    hostname = (
        parsed.hostname
        or ""
    ).lower().removeprefix("www.")

    if not scheme or not hostname:
        return url.strip()

    port = parsed.port

    if (
        port is None
        or (
            scheme == "https"
            and port == 443
        )
        or (
            scheme == "http"
            and port == 80
        )
    ):
        netloc = hostname
    else:
        netloc = f"{hostname}:{port}"

    path = re.sub(
        r"/+",
        "/",
        parsed.path or "/",
    )

    if path != "/":
        path = path.rstrip("/")

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
        if (
            key.lower()
            not in TRACKING_PARAMETERS
            and not key.lower().startswith(
                "utm_"
            )
        )
    ]

    return urlunsplit(
        (
            scheme,
            netloc,
            path,
            urlencode(query_pairs),
            "",
        )
    )


def hostname_for_url(
    url: str,
) -> str:
    return (
        urlsplit(url).hostname
        or ""
    ).lower().removeprefix("www.")


def domain_matches(
    hostname: str,
    official_domain: str,
) -> bool:
    normalized = (
        official_domain
        .lower()
        .strip()
        .removeprefix("www.")
    )

    return (
        hostname == normalized
        or hostname.endswith(
            "." + normalized
        )
    )


def tokenize(
    value: str,
) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9][a-z0-9&.-]{1,}",
            value.lower(),
        )
        if (
            len(token) >= 3
            and token not in STOPWORDS
        )
    }


def is_low_value_result(
    result: ProviderSearchResult,
) -> bool:
    combined = (
        result.title
        + " "
        + result.snippet
        + " "
        + result.url
    ).lower()

    return any(
        re.search(
            pattern,
            combined,
        )
        for pattern in LOW_VALUE_PATTERNS
    )


def score_result(
    result: ProviderSearchResult,
    plan: ResearchPlan,
) -> tuple[
    float,
    tuple[str, ...],
    bool,
]:
    combined = " ".join(
        (
            result.title,
            result.snippet,
            result.url,
        )
    ).lower()

    hostname = hostname_for_url(
        result.url
    )

    authority = authority_for_url(
        result.url
    )

    official = (
        authority is not None
        or any(
            domain_matches(
                hostname,
                domain,
            )
            for domain in plan.official_domains
        )
    )

    question_terms = tokenize(
        plan.question
    )

    entity_terms = set()

    for entity in plan.entities:
        entity_terms.update(
            tokenize(entity)
        )

    geography_terms = set()

    for geography in plan.geography:
        geography_terms.update(
            tokenize(geography)
        )

    intent_terms = tokenize(
        plan.intent
    )

    matched = {
        term
        for term in (
            question_terms
            | entity_terms
            | geography_terms
            | intent_terms
        )
        if term in combined
    }

    score = 0.0

    score += len(
        question_terms & matched
    ) * 1.2

    score += len(
        entity_terms & matched
    ) * 2.5

    score += len(
        geography_terms & matched
    ) * 2.0

    score += len(
        intent_terms & matched
    ) * 0.75

    if official:
        score += 12.0

    if authority is not None:
        if authority.tier == "controlling":
            score += 10.0
        elif authority.tier == "primary":
            score += 7.0
        else:
            score += 4.0

    if hostname.endswith(".gov"):
        score += 10.0

    if hostname.endswith(".edu"):
        score += 5.0

    title_lower = result.title.lower()

    for entity in plan.entities:
        if entity.lower() in title_lower:
            score += 4.0

    for geography in plan.geography:
        if geography.lower() in title_lower:
            score += 3.0

    if result.published_at:
        score += 1.0

    if result.snippet:
        score += min(
            len(result.snippet) / 500,
            1.5,
        )

    if is_low_value_result(result):
        score -= 15.0

    return (
        round(score, 3),
        tuple(sorted(matched)),
        official,
    )


@dataclass
class DiscoveryCoordinator:
    providers: tuple[SearchProvider, ...]
    maximum_results_per_query: int = 10
    maximum_candidates: int = 30

    def discover(
        self,
        plan: ResearchPlan,
    ) -> DiscoveryReport:
        failures: list[
            DiscoveryFailure
        ] = []

        raw_results: list[
            ProviderSearchResult
        ] = []

        provider_counts: dict[
            str,
            int
        ] = {}

        queries = list(
            plan.search_queries
        )

        for domain in plan.official_domains:
            queries.append(
                f"site:{domain} {plan.question}"
            )

        queries = list(
            dict.fromkeys(
                query.strip()
                for query in queries
                if query.strip()
            )
        )

        timelimit = {
            "live": "d",
            "recent": "m",
            "historical": None,
            "not_time_sensitive": None,
        }.get(
            plan.freshness
        )

        for provider in self.providers:
            provider_name = getattr(
                provider,
                "provider_name",
                type(provider).__name__,
            )

            for query in queries:
                try:
                    results = provider.search(
                        query,
                        max_results=(
                            self.maximum_results_per_query
                        ),
                        timelimit=timelimit,
                    )

                except (
                    SearchProviderError,
                    Exception,
                ) as exc:
                    failures.append(
                        DiscoveryFailure(
                            provider=provider_name,
                            query=query,
                            error=(
                                f"{type(exc).__name__}: "
                                f"{exc}"
                            ),
                        )
                    )
                    continue

                provider_counts[
                    provider_name
                ] = (
                    provider_counts.get(
                        provider_name,
                        0,
                    )
                    + len(results)
                )

                raw_results.extend(
                    results
                )

        grouped: dict[
            str,
            list[ProviderSearchResult]
        ] = {}

        for result in raw_results:
            canonical = canonicalize_url(
                result.url
            )

            if not canonical:
                continue

            grouped.setdefault(
                canonical,
                [],
            ).append(result)

        candidates: list[
            DiscoveryCandidate
        ] = []

        for canonical_url, matches in (
            grouped.items()
        ):
            best_result = None
            best_score = float("-inf")
            best_terms: tuple[str, ...] = ()
            best_official = False

            duplicate_queries = tuple(
                dict.fromkeys(
                    result.query
                    for result in matches
                    if result.query
                )
            )

            for result in matches:
                normalized_result = (
                    ProviderSearchResult(
                        provider=result.provider,
                        title=result.title,
                        url=canonical_url,
                        snippet=result.snippet,
                        published_at=(
                            result.published_at
                        ),
                        source_engine=(
                            result.source_engine
                        ),
                        query=result.query,
                        metadata=result.metadata,
                    )
                )

                (
                    score,
                    matched_terms,
                    official,
                ) = score_result(
                    normalized_result,
                    plan,
                )

                if score > best_score:
                    best_result = (
                        normalized_result
                    )
                    best_score = score
                    best_terms = matched_terms
                    best_official = official

            if best_result is None:
                continue

            candidates.append(
                DiscoveryCandidate(
                    result=best_result,
                    score=best_score,
                    matched_terms=best_terms,
                    official_domain=(
                        best_official
                    ),
                    duplicate_queries=(
                        duplicate_queries
                    ),
                )
            )

        candidates.sort(
            key=lambda item: (
                item.official_domain,
                item.score,
                bool(
                    item.result.published_at
                ),
            ),
            reverse=True,
        )

        return DiscoveryReport(
            plan=plan,
            candidates=tuple(
                candidates[
                    : self.maximum_candidates
                ]
            ),
            failures=tuple(failures),
            raw_result_count=len(
                raw_results
            ),
            deduplicated_result_count=len(
                grouped
            ),
            provider_counts=(
                provider_counts
            ),
        )
