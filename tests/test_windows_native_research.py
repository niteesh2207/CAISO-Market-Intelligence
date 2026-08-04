import json

from market_intelligence.research.gdelt_client import (
    GdeltClient,
)
from market_intelligence.research.models import (
    SearchResult,
    SourceTier,
)
from market_intelligence.research.ollama_client import (
    OllamaClient,
)
from market_intelligence.research.source_ranker import (
    classify_source,
    rank_results,
)


def test_classifies_controlling_sources():
    assert (
        classify_source(
            "https://www.eia.gov/todayinenergy/"
        )
        == SourceTier.CONTROLLING
    )

    assert (
        classify_source(
            "https://www.ferc.gov/news-events"
        )
        == SourceTier.CONTROLLING
    )


def test_primary_source_ranks_above_blog():
    results = [
        SearchResult(
            title="Energy commentary",
            url="https://example.com/post",
            snippet="CAISO load and generation",
        ),
        SearchResult(
            title="Official demand data",
            url="https://www.eia.gov/electricity/",
            snippet="CAISO hourly demand data",
        ),
    ]

    ranked = rank_results(
        results,
        "What is CAISO hourly demand?",
    )

    assert (
        ranked[0].source_tier
        == SourceTier.CONTROLLING
    )


def test_gdelt_builds_json_article_query():
    client = GdeltClient(
        http_get=lambda *_: b'{"articles":[]}'
    )

    url = client.build_url(
        "Henry Hub natural gas",
        max_records=10,
        timespan="3days",
    )

    assert "mode=artlist" in url
    assert "format=json" in url
    assert "maxrecords=10" in url
    assert "timespan=3days" in url


def test_gdelt_parses_articles():
    payload = {
        "articles": [
            {
                "title": "Energy market update",
                "url": "https://example.com/article",
                "domain": "example.com",
                "seendate": "20260804T120000Z",
                "language": "English",
                "sourcecountry": "United States",
            }
        ]
    }

    client = GdeltClient(
        http_get=lambda *_: json.dumps(
            payload
        ).encode("utf-8")
    )

    results = client.search(
        "energy market",
    )

    assert len(results) == 1
    assert (
        results[0].title
        == "Energy market update"
    )


def test_ollama_parses_structured_answer():
    response = {
        "message": {
            "content": json.dumps(
                {
                    "answer": "CAISO operates the grid.",
                    "explanation": (
                        "The supplied evidence says so."
                    ),
                    "confidence": "high",
                    "limitations": [],
                }
            )
        }
    }

    client = OllamaClient(
        http_post=lambda *_: json.dumps(
            response
        ).encode("utf-8")
    )

    result = client.structured_answer(
        question="What does CAISO operate?",
        evidence_text=(
            "CAISO operates California's "
            "high-voltage grid."
        ),
    )

    assert result["confidence"] == "high"
    assert "CAISO" in result["answer"]

def test_gdelt_retries_after_rate_limit(monkeypatch):
    from email.message import Message
    from urllib.error import HTTPError

    calls = {"count": 0}

    def fake_http_get(*_):
        calls["count"] += 1

        if calls["count"] == 1:
            headers = Message()
            headers["Retry-After"] = "0"

            raise HTTPError(
                url="https://example.invalid",
                code=429,
                msg="Too Many Requests",
                hdrs=headers,
                fp=None,
            )

        return b'{"articles":[]}'

    monkeypatch.setattr(
        "market_intelligence.research.gdelt_client.time.sleep",
        lambda *_: None,
    )

    client = GdeltClient(
        http_get=fake_http_get
    )

    results = client.search(
        "energy market"
    )

    assert results == []
    assert calls["count"] == 2
