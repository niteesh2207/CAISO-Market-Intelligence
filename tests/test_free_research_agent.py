from market_intelligence.research.free_research_agent import (
    FreeResearchAgent,
)
from market_intelligence.research.models import (
    SearchResult,
    SourceTier,
)
from market_intelligence.research.page_fetcher import (
    FetchedPage,
)


class FakeDiscovery:
    def search(self, *_args, **_kwargs):
        return [
            SearchResult(
                title="Official CAISO information",
                url="https://www.caiso.com/example",
                snippet="California grid operations",
                domain="caiso.com",
                source_tier=SourceTier.CONTROLLING,
            )
        ]


class FailingDiscovery:
    def search(self, *_args, **_kwargs):
        from market_intelligence.research.gdelt_client import (
            GdeltError,
        )

        raise GdeltError(
            "Provider temporarily unavailable."
        )


class FakeFetcher:
    def fetch(self, url):
        return FetchedPage(
            requested_url=url,
            final_url=url,
            title="Official CAISO information",
            text=(
                "CAISO operates the wholesale "
                "electricity market and manages "
                "the high-voltage transmission "
                "system serving most of California."
            ),
            content_type="text/html",
            retrieved_at="2026-08-04T12:00:00+00:00",
            response_bytes=500,
        )


class FakeOllama:
    def structured_answer(
        self,
        *,
        question,
        evidence_text,
    ):
        assert question
        assert "CAISO" in evidence_text

        return {
            "answer": (
                "CAISO manages wholesale power-market "
                "operations and the high-voltage grid "
                "serving most of California."
            ),
            "explanation": (
                "The answer is based on the retrieved "
                "official CAISO evidence."
            ),
            "confidence": "high",
            "limitations": [],
        }


def test_free_research_agent_returns_grounded_answer():
    agent = FreeResearchAgent(
        gdelt=FakeDiscovery(),
        fetcher=FakeFetcher(),
        ollama=FakeOllama(),
    )

    result = agent.answer(
        "What does CAISO operate?"
    )

    assert result.status == "answered"
    assert result.confidence == "high"
    assert len(result.sources) == 1
    assert result.sources[0].primary is True
    assert result.sources[0].url.startswith(
        "https://www.caiso.com/"
    )


def test_free_research_agent_fails_safely_without_sources():
    agent = FreeResearchAgent(
        gdelt=FailingDiscovery(),
        fetcher=FakeFetcher(),
        ollama=FakeOllama(),
    )

    result = agent.answer(
        "Why did power prices change?"
    )

    assert result.status == "research_unavailable"
    assert result.confidence == "insufficient"
    assert result.sources == ()
    assert result.limitations
