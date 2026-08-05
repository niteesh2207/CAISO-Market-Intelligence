import json

from market_intelligence.research.ddgs_provider import (
    DdgsSearchProvider,
)
from market_intelligence.research.query_planner import (
    OllamaQueryPlanner,
)


def test_query_planner_accepts_energy_adjacent_load():
    plan_payload = {
        "is_energy_related": True,
        "domain": "electricity_infrastructure",
        "intent": "location_and_grid_impact",
        "geography": [
            "SDG&E",
            "California",
        ],
        "entities": [
            "data centers",
        ],
        "freshness": "recent",
        "search_queries": [
            (
                "SDG&E service territory "
                "data center locations"
            ),
            (
                "site:sdge.com data center "
                "electricity demand"
            ),
            (
                "San Diego data centers "
                "grid load"
            ),
            (
                "California data center "
                "energy demand news"
            ),
        ],
        "official_domains": [
            "sdge.com",
            "caiso.com",
            "energy.ca.gov",
        ],
        "reasoning_summary": (
            "Data centers are major electrical "
            "loads relevant to grid planning."
        ),
    }

    envelope = {
        "message": {
            "content": json.dumps(
                plan_payload
            )
        }
    }

    planner = OllamaQueryPlanner(
        http_post=lambda *_: json.dumps(
            envelope
        ).encode("utf-8")
    )

    plan = planner.plan(
        "Where are the data centers "
        "in the SDG&E region?"
    )

    assert plan.is_energy_related is True
    assert (
        plan.domain
        == "electricity_infrastructure"
    )
    assert "data centers" in plan.entities
    assert len(plan.search_queries) >= 3
    assert "sdge.com" in plan.official_domains


def test_ddgs_provider_normalizes_results():
    def fake_search(*_args, **_kwargs):
        return [
            {
                "title": "Official utility filing",
                "href": (
                    "https://www.sdge.com/"
                    "regulatory-filing"
                ),
                "body": (
                    "Grid planning and large-load "
                    "information."
                ),
                "source": "Bing",
            },
            {
                "title": "Official utility filing",
                "href": (
                    "https://www.sdge.com/"
                    "regulatory-filing"
                ),
                "body": "Duplicate",
            },
        ]

    provider = DdgsSearchProvider(
        search_function=fake_search
    )

    results = provider.search(
        "SDG&E data centers",
        max_results=10,
    )

    assert len(results) == 1
    assert results[0].provider == "ddgs_web"
    assert results[0].source_engine == "Bing"
    assert results[0].url.startswith(
        "https://www.sdge.com/"
    )
