from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.request import Request, urlopen

from market_intelligence.research.discovery_models import (
    ResearchPlan,
)


class QueryPlannerError(RuntimeError):
    pass


HttpPost = Callable[
    [str, bytes, dict[str, str], float],
    bytes,
]


def default_http_post(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
) -> bytes:
    request = Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )

    with urlopen(
        request,
        timeout=timeout,
    ) as response:
        return response.read()


PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_energy_related": {
            "type": "boolean",
        },
        "domain": {
            "type": "string",
        },
        "intent": {
            "type": "string",
        },
        "geography": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "entities": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "freshness": {
            "type": "string",
            "enum": [
                "live",
                "recent",
                "historical",
                "not_time_sensitive",
            ],
        },
        "search_queries": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "minItems": 3,
            "maxItems": 8,
        },
        "official_domains": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "reasoning_summary": {
            "type": "string",
        },
    },
    "required": [
        "is_energy_related",
        "domain",
        "intent",
        "geography",
        "entities",
        "freshness",
        "search_queries",
        "official_domains",
        "reasoning_summary",
    ],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """
You are an energy-market research planner.

Your job is to determine whether the question is directly or
indirectly related to energy, electricity, fuels, infrastructure,
utilities, grid planning, energy-intensive loads, regulation,
generation, transmission, weather-driven demand, company assets,
commodities, emissions or energy finance.

Questions about data centers, industrial loads, utilities, local
infrastructure, construction projects and company facilities can be
energy-related when they affect electricity demand, grid planning,
generation, transmission, fuel demand or market conditions.

Do not answer the question.

Return only a structured research plan.

Generate:
1. a broad web-search query;
2. an official-source query;
3. a current-news query;
4. additional site-specific queries when appropriate.

Prefer official domains such as:
eia.gov, ferc.gov, energy.gov, nrc.gov, noaa.gov, weather.gov,
caiso.com, ercot.com, pjm.com, misoenergy.org, spp.org, nyiso.com,
iso-ne.com, nerc.com, sec.gov and relevant utility domains.
""".strip()


@dataclass(frozen=True)
class OllamaQueryPlanner:
    model: str = "gemma3:4b"
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 180.0
    http_post: HttpPost = default_http_post

    def plan(
        self,
        question: str,
    ) -> ResearchPlan:
        cleaned = question.strip()

        if not cleaned:
            raise ValueError(
                "Question cannot be blank."
            )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": cleaned,
                },
            ],
            "format": PLAN_SCHEMA,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        }

        try:
            raw = self.http_post(
                (
                    self.base_url.rstrip("/")
                    + "/api/chat"
                ),
                json.dumps(payload).encode(
                    "utf-8"
                ),
                {
                    "Content-Type": (
                        "application/json"
                    ),
                    "Accept": "application/json",
                },
                self.timeout_seconds,
            )

            envelope = json.loads(
                raw.decode(
                    "utf-8",
                    errors="replace",
                )
            )

            result = json.loads(
                envelope["message"]["content"]
            )

        except Exception as exc:
            raise QueryPlannerError(
                f"Query planning failed: {exc}"
            ) from exc

        queries = tuple(
            dict.fromkeys(
                query.strip()
                for query in result[
                    "search_queries"
                ]
                if query.strip()
            )
        )

        if len(queries) < 3:
            raise QueryPlannerError(
                "Planner returned fewer than "
                "three usable search queries."
            )

        return ResearchPlan(
            question=cleaned,
            is_energy_related=bool(
                result["is_energy_related"]
            ),
            domain=str(
                result["domain"]
            ).strip(),
            intent=str(
                result["intent"]
            ).strip(),
            geography=tuple(
                str(item).strip()
                for item in result["geography"]
                if str(item).strip()
            ),
            entities=tuple(
                str(item).strip()
                for item in result["entities"]
                if str(item).strip()
            ),
            freshness=str(
                result["freshness"]
            ).strip(),
            search_queries=queries,
            official_domains=tuple(
                dict.fromkeys(
                    str(item)
                    .lower()
                    .strip()
                    .removeprefix("www.")
                    for item in result[
                        "official_domains"
                    ]
                    if str(item).strip()
                )
            ),
            reasoning_summary=str(
                result["reasoning_summary"]
            ).strip(),
            metadata={
                "planner": "ollama",
                "model": self.model,
            },
        )


def default_query_planner() -> OllamaQueryPlanner:
    model = os.getenv(
        "OLLAMA_MODEL",
        "gemma3:4b",
    ).strip()

    return OllamaQueryPlanner(
        model=model or "gemma3:4b"
    )
