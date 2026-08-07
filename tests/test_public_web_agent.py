from market_intelligence.research.discovery_models import (
    ProviderSearchResult,
)
from market_intelligence.research.page_fetcher import FetchedPage
from market_intelligence.research.public_web_agent import (
    PublicWebResearchAgent,
)


class FakeSearch:
    def search(self, query, **_kwargs):
        assert "CAISO" in query
        return [
            ProviderSearchResult(
                provider="ddgs_web",
                title="Today's Outlook",
                url="https://www.caiso.com/todays-outlook/prices",
                snippet="Current CAISO market-price information.",
                query=query,
            ),
            ProviderSearchResult(
                provider="ddgs_web",
                title="Licensed market page",
                url="https://www.ice.com/example",
                snippet="Licensed content",
                query=query,
            ),
        ]


class FakeFetcher:
    def fetch(self, url):
        return FetchedPage(
            requested_url=url,
            final_url=url,
            title="Today's Outlook | California ISO",
            text=(
                "California ISO publishes current wholesale market prices "
                "and explains that they reflect the cost of generating and "
                "delivering electricity from price nodes."
            ),
            content_type="text/html",
            retrieved_at="2026-08-06T18:00:00+00:00",
            response_bytes=500,
        )


def test_public_agent_searches_fetches_and_cites_approved_pages():
    agent = PublicWebResearchAgent(
        search_provider=FakeSearch(),
        fetcher=FakeFetcher(),
    )

    result = agent.answer(
        "What does CAISO publish about current prices?",
        allowed_domains=["caiso.com"],
    )

    assert result.confidence == "low"
    assert result.discovered_results == 2
    assert result.retrieved_pages == 1
    assert len(result.sources) == 1
    assert result.sources[0].primary is True
    assert "[1]" in result.answer
    assert "ice.com" not in result.answer
