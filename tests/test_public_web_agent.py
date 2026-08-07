from datetime import datetime, timedelta, timezone

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
    assert result.sources[0].freshness == "live"
    assert "[1]" in result.answer
    assert "ice.com" not in result.answer


class RankedSearch:
    def __init__(self, results):
        self.results = results
        self.timelimits = []

    def search(self, _query, **kwargs):
        self.timelimits.append(kwargs["timelimit"])
        return self.results


class RecordingFetcher:
    def __init__(self):
        self.urls = []

    def fetch(self, url):
        self.urls.append(url)
        return FetchedPage(
            requested_url=url,
            final_url=url,
            title="Current official operating data",
            text=(
                "CAISO current hydro generation and operating capacity "
                "information was updated for the latest operating day."
            ),
            content_type="text/html",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            response_bytes=400,
        )


def test_current_question_prioritizes_recent_primary_evidence():
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=3)).isoformat()
    search = RankedSearch([
        ProviderSearchResult(
            provider="ddgs_web",
            title="CAISO historical hydro report",
            url="https://www.caiso.com/documents/2021-hydro-report.pdf",
            snippet="Hydro generation capacity in 2021.",
            published_at="2021-05-01T00:00:00+00:00",
        ),
        ProviderSearchResult(
            provider="ddgs_web",
            title="Latest CAISO hydro operating data",
            url="https://www.caiso.com/current-hydro-data",
            snippet="Current hydro generation and operating capacity.",
            published_at=recent,
        ),
        ProviderSearchResult(
            provider="ddgs_web",
            title="Pages - 404",
            url="https://www.caiso.com/missing",
            snippet="Page not found.",
            published_at=recent,
        ),
    ])
    fetcher = RecordingFetcher()

    result = PublicWebResearchAgent(
        search_provider=search,
        fetcher=fetcher,
    ).answer(
        "What hydro is running at maximum capacity in CAISO now?",
        allowed_domains=["caiso.com", "eia.gov"],
    )

    assert search.timelimits == [None]
    assert fetcher.urls == [
        "https://www.caiso.com/todays-outlook/supply",
        "https://www.caiso.com/current-hydro-data",
    ]
    assert result.confidence == "medium"
    assert result.sources[0].freshness == "live"
    assert result.sources[1].freshness == "current"
    assert result.sources[1].published_at == recent
    assert "2021-hydro-report" not in result.answer
    assert "does not identify individual hydroelectric facilities" in result.answer
    assert "no specific hydro plant can be verified" in result.answer


def test_current_question_withholds_claim_when_freshness_is_unknown():
    search = RankedSearch([
        ProviderSearchResult(
            provider="ddgs_web",
            title="CAISO congestion overview",
            url="https://www.caiso.com/congestion-overview",
            snippet="General information about CAISO congestion.",
        ),
    ])

    result = PublicWebResearchAgent(
        search_provider=search,
        fetcher=RecordingFetcher(),
    ).answer(
        "What is current CAISO congestion?",
        allowed_domains=["caiso.com"],
    )

    assert result.confidence == "insufficient"
    assert "could not verify a current answer" in result.answer
    assert result.sources[0].freshness == "unknown"


class FocusedFallbackSearch:
    def __init__(self):
        self.queries = []

    def search(self, query, **_kwargs):
        self.queries.append(query)
        if len(self.queries) == 1:
            return []
        assert query == "los banos panoche congestion CAISO 2026"
        return [
            ProviderSearchResult(
                provider="ddgs_web",
                title="2025-2026 transmission plan: Path 15 congestion",
                url="https://www.caiso.com/documents/path-15-plan.pdf",
                snippet=(
                    "The latest plan evaluates Los Banos and Panoche "
                    "congestion and proposed Path 15 reinforcements."
                ),
                published_at="2026-05-19T00:00:00+00:00",
            ),
        ]


def test_empty_authority_search_retries_a_focused_freshness_query():
    search = FocusedFallbackSearch()
    result = PublicWebResearchAgent(
        search_provider=search,
        fetcher=RecordingFetcher(),
    ).answer(
        "Give me insights about Los Banos Panoche congestion now",
        allowed_domains=["caiso.com", "ferc.gov"],
    )

    assert len(search.queries) == 2
    assert result.sources[0].url.endswith("path-15-plan.pdf")
    assert result.sources[0].freshness == "historical"
    assert result.confidence == "insufficient"
    assert "2026-05-19" in result.answer
