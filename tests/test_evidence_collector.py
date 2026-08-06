from market_intelligence.research.discovery_coordinator import (
    DiscoveryCandidate,
    DiscoveryReport,
)
from market_intelligence.research.discovery_models import (
    ProviderSearchResult,
    ResearchPlan,
)
from market_intelligence.research.evidence_collector import (
    EvidenceCollector,
)
from market_intelligence.research.page_fetcher import (
    FetchedPage,
)


class FakeFetcher:
    def fetch(self, url):
        if "sdge.com" in url:
            return FetchedPage(
                requested_url=url,
                final_url=url,
                title=(
                    "SDG&E Large Load "
                    "Interconnection"
                ),
                text=(
                    "SDG&E provides interconnection "
                    "and planning information for "
                    "large electrical loads including "
                    "data centers in the San Diego "
                    "service territory. "
                    * 20
                ),
                content_type="text/html",
                retrieved_at=(
                    "2026-08-05T10:00:00Z"
                ),
                response_bytes=5_000,
            )

        return FetchedPage(
            requested_url=url,
            final_url=url,
            title="My Energy Center Login",
            text=(
                "Sign in to manage your account. "
                * 30
            ),
            content_type="text/html",
            retrieved_at=(
                "2026-08-05T10:00:00Z"
            ),
            response_bytes=2_000,
        )


def sample_report():
    plan = ResearchPlan(
        question=(
            "Where are the data centers "
            "in the SDG&E region?"
        ),
        is_energy_related=True,
        domain=(
            "electricity_infrastructure"
        ),
        intent="location_and_grid_impact",
        geography=(
            "SDG&E",
            "San Diego",
        ),
        entities=(
            "data centers",
        ),
        freshness="recent",
        search_queries=(
            "SDG&E data centers",
            "San Diego large loads",
            "site:sdge.com data centers",
        ),
        official_domains=(
            "sdge.com",
        ),
        reasoning_summary=(
            "Data centers are large loads."
        ),
    )

    candidates = (
        DiscoveryCandidate(
            result=ProviderSearchResult(
                provider="fake",
                title=(
                    "SDG&E Large Load "
                    "Interconnection"
                ),
                url=(
                    "https://www.sdge.com/"
                    "large-loads"
                ),
                snippet=(
                    "Official utility planning "
                    "information."
                ),
                query="site:sdge.com data centers",
            ),
            score=30.0,
            matched_terms=(
                "centers",
                "sdg&e",
            ),
            official_domain=True,
        ),
        DiscoveryCandidate(
            result=ProviderSearchResult(
                provider="fake",
                title="My Energy Center Login",
                url=(
                    "https://myenergycenter.com/"
                    "portal/register"
                ),
                snippet="Account portal.",
                query="SDG&E data centers",
            ),
            score=1.0,
            matched_terms=(),
            official_domain=False,
        ),
    )

    return DiscoveryReport(
        plan=plan,
        candidates=candidates,
        failures=(),
        raw_result_count=2,
        deduplicated_result_count=2,
        provider_counts={
            "fake": 2,
        },
    )


def test_evidence_collector_accepts_official_page():
    collector = EvidenceCollector(
        fetcher=FakeFetcher()
    )

    packet = collector.collect(
        sample_report()
    )

    assert packet.sufficient is True
    assert len(packet.documents) == 1
    assert (
        packet.documents[0].official
        is True
    )
    assert (
        packet.controlling_source_count
        == 1
    )


def test_irrelevant_login_page_is_rejected():
    collector = EvidenceCollector(
        fetcher=FakeFetcher()
    )

    packet = collector.collect(
        sample_report()
    )

    assert all(
        "myenergycenter.com"
        not in document.url
        for document in packet.documents
    )
    assert packet.failures
