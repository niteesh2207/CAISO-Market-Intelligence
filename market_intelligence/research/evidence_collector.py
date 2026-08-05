from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from market_intelligence.research.authority_registry import (
    authority_for_url,
)
from market_intelligence.research.discovery_coordinator import (
    DiscoveryCandidate,
    DiscoveryReport,
    tokenize,
)
from market_intelligence.research.page_fetcher import (
    FetchedPage,
    PageFetchError,
    PageFetcher,
)


@dataclass(frozen=True)
class EvidenceDocument:
    title: str
    url: str
    provider: str
    text: str
    retrieved_at: str
    source_tier: str
    official: bool
    discovery_score: float
    relevance_score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceFailure:
    url: str
    reason: str


@dataclass(frozen=True)
class EvidencePacket:
    question: str
    documents: tuple[EvidenceDocument, ...]
    failures: tuple[EvidenceFailure, ...]
    controlling_source_count: int
    independent_domain_count: int
    sufficient: bool
    sufficiency_reason: str


def page_relevance(
    page: FetchedPage,
    candidate: DiscoveryCandidate,
    report: DiscoveryReport,
) -> tuple[float, tuple[str, ...]]:
    combined = (
        page.title
        + " "
        + page.text[:12_000]
    ).lower()

    question_terms = tokenize(
        report.plan.question
    )

    entity_terms = set()

    for value in report.plan.entities:
        entity_terms.update(
            tokenize(value)
        )

    geography_terms = set()

    for value in report.plan.geography:
        geography_terms.update(
            tokenize(value)
        )

    required_terms = (
        question_terms
        | entity_terms
        | geography_terms
    )

    matched = {
        term
        for term in required_terms
        if term in combined
    }

    score = 0.0

    score += len(
        question_terms & matched
    ) * 1.0

    score += len(
        entity_terms & matched
    ) * 3.0

    score += len(
        geography_terms & matched
    ) * 2.5

    if page.title:
        title_lower = page.title.lower()

        for entity in report.plan.entities:
            if entity.lower() in title_lower:
                score += 4.0

        for geography in report.plan.geography:
            if geography.lower() in title_lower:
                score += 3.0

    authority = authority_for_url(
        page.final_url
    )

    if authority is not None:
        score += 6.0

    score += min(
        len(page.text) / 8_000,
        2.0,
    )

    score += min(
        candidate.score / 20,
        2.0,
    )

    return (
        round(score, 3),
        tuple(sorted(matched)),
    )


@dataclass
class EvidenceCollector:
    fetcher: PageFetcher
    maximum_candidates_to_fetch: int = 12
    maximum_documents: int = 6
    minimum_page_relevance: float = 5.0
    minimum_text_characters: int = 300

    def collect(
        self,
        report: DiscoveryReport,
    ) -> EvidencePacket:
        documents: list[
            EvidenceDocument
        ] = []

        failures: list[
            EvidenceFailure
        ] = []

        seen_domains: set[str] = set()

        for candidate in report.candidates[
            : self.maximum_candidates_to_fetch
        ]:
            if (
                len(documents)
                >= self.maximum_documents
            ):
                break

            url = candidate.result.url

            try:
                page = self.fetcher.fetch(
                    url
                )
            except PageFetchError as exc:
                failures.append(
                    EvidenceFailure(
                        url=url,
                        reason=str(exc),
                    )
                )
                continue

            if (
                len(page.text)
                < self.minimum_text_characters
            ):
                failures.append(
                    EvidenceFailure(
                        url=page.final_url,
                        reason=(
                            "Insufficient extracted "
                            "page text."
                        ),
                    )
                )
                continue

            (
                relevance_score,
                matched_terms,
            ) = page_relevance(
                page,
                candidate,
                report,
            )

            if (
                relevance_score
                < self.minimum_page_relevance
            ):
                failures.append(
                    EvidenceFailure(
                        url=page.final_url,
                        reason=(
                            "Extracted page did not "
                            "meet the relevance gate."
                        ),
                    )
                )
                continue

            hostname = (
                urlsplit(
                    page.final_url
                ).hostname
                or ""
            ).lower().removeprefix("www.")

            authority = authority_for_url(
                page.final_url
            )

            source_tier = (
                authority.tier
                if authority is not None
                else "supporting"
            )

            documents.append(
                EvidenceDocument(
                    title=(
                        page.title
                        or candidate.result.title
                    ),
                    url=page.final_url,
                    provider=(
                        authority.organization
                        if authority is not None
                        else hostname
                    ),
                    text=page.text,
                    retrieved_at=(
                        page.retrieved_at
                    ),
                    source_tier=source_tier,
                    official=(
                        authority is not None
                        or candidate.official_domain
                    ),
                    discovery_score=(
                        candidate.score
                    ),
                    relevance_score=(
                        relevance_score
                    ),
                    matched_terms=(
                        matched_terms
                    ),
                )
            )

            if hostname:
                seen_domains.add(hostname)

        controlling_count = sum(
            document.source_tier
            in {
                "controlling",
                "primary",
            }
            for document in documents
        )

        independent_domains = {
            (
                urlsplit(document.url)
                .hostname
                or ""
            )
            .lower()
            .removeprefix("www.")
            for document in documents
        }

        independent_domains.discard("")

        sufficient = (
            controlling_count >= 1
            or len(independent_domains) >= 2
        )

        if controlling_count >= 1:
            reason = (
                "At least one controlling or "
                "primary source passed the "
                "evidence gate."
            )
        elif len(independent_domains) >= 2:
            reason = (
                "At least two independent "
                "supporting domains passed the "
                "evidence gate."
            )
        else:
            reason = (
                "The evidence packet lacks a "
                "controlling source or two "
                "independent supporting sources."
            )

        return EvidencePacket(
            question=report.plan.question,
            documents=tuple(documents),
            failures=tuple(failures),
            controlling_source_count=(
                controlling_count
            ),
            independent_domain_count=len(
                independent_domains
            ),
            sufficient=sufficient,
            sufficiency_reason=reason,
        )
