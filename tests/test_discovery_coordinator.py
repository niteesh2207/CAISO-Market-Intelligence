from market_intelligence.research.discovery_coordinator import (
    DiscoveryCoordinator,
    canonicalize_url,
)
from market_intelligence.research.discovery_models import (
    ProviderSearchResult,
    ResearchPlan,
)
from market_intelligence.research.search_provider import (
    SearchProviderError,
)


class FakeProvider:
    provider_name = "fake_web"

    def search(
        self,
        query,
        *,
        max_results,
        timelimit,
    ):
        if "site:sdge.com" in query:
            return [
                ProviderSearchResult(
                    provider=self.provider_name,
                    title=(
                        "SDG&E Large Load "
                        "Interconnection Information"
                    ),
                    url=(
                        "https://www.sdge.com/"
                        "large-loads/?utm_source=test"
                    ),
                    snippet=(
                        "Official SDG&E information "
                        "for data centers and large "
                        "electrical loads."
                    ),
                    query=query,
                )
            ]

        return [
            ProviderSearchResult(
                provider=self.provider_name,
                title=(
                    "San Diego Data Center "
                    "Development"
                ),
                url=(
                    "https://example.com/"
                    "san-diego-data-center"
                ),
                snippet=(
                    "A data center project in the "
                    "San Diego region with utility "
                    "load requirements."
                ),
                query=query,
            ),
            ProviderSearchResult(
                provider=self.provider_name,
                title="My Energy Center Login",
                url=(
                    "https://myenergycenter.com/"
                    "portal/Register"
                ),
                snippet=(
                    "Register or sign in to your "
                    "energy account."
                ),
                query=query,
            ),
        ]


class FailingProvider:
    provider_name = "broken_provider"

    def search(
        self,
        query,
        *,
        max_results,
        timelimit,
    ):
        raise SearchProviderError(
            "simulated provider failure"
        )


def sample_plan():
    return ResearchPlan(
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
            (
                "SDG&E service territory "
                "data center locations"
            ),
            (
                "San Diego data center "
                "electricity load"
            ),
            (
                "California data center "
                "grid planning"
            ),
        ),
        official_domains=(
            "sdge.com",
            "caiso.com",
        ),
        reasoning_summary=(
            "Data centers are large loads."
        ),
    )


def test_canonicalize_url_removes_tracking():
    value = canonicalize_url(
        (
            "https://www.sdge.com/"
            "large-loads/?utm_source=test"
            "&ref=home"
        )
    )

    assert value == (
        "https://sdge.com/large-loads"
    )


def test_official_result_ranks_first():
    coordinator = DiscoveryCoordinator(
        providers=(FakeProvider(),)
    )

    report = coordinator.discover(
        sample_plan()
    )

    assert report.candidates
    assert (
        report.candidates[0]
        .official_domain
        is True
    )
    assert (
        "sdge.com"
        in report.candidates[0]
        .result.url
    )


def test_low_value_login_result_is_demoted():
    coordinator = DiscoveryCoordinator(
        providers=(FakeProvider(),)
    )

    report = coordinator.discover(
        sample_plan()
    )

    urls = [
        candidate.result.url
        for candidate in report.candidates
    ]

    assert urls[-1].startswith(
        "https://myenergycenter.com/"
    )


def test_provider_failure_does_not_stop_search():
    coordinator = DiscoveryCoordinator(
        providers=(
            FailingProvider(),
            FakeProvider(),
        )
    )

    report = coordinator.discover(
        sample_plan()
    )

    assert report.candidates
    assert report.failures
    assert (
        report.failures[0].provider
        == "broken_provider"
    )
