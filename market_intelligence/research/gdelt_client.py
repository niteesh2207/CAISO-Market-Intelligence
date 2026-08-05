from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from market_intelligence.research.models import (
    SearchResult,
)


class GdeltError(RuntimeError):
    pass


HttpGet = Callable[[str, dict[str, str], float], bytes]


def default_http_get(
    url: str,
    headers: dict[str, str],
    timeout: float,
) -> bytes:
    request = Request(
        url,
        headers=headers,
        method="GET",
    )

    with urlopen(
        request,
        timeout=timeout,
    ) as response:
        return response.read()


@dataclass(frozen=True)
class GdeltClient:
    endpoint: str = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
    )
    timeout_seconds: float = 30.0
    http_get: HttpGet = default_http_get

    def build_url(
        self,
        query: str,
        *,
        max_records: int = 25,
        timespan: str = "7days",
    ) -> str:
        if not query.strip():
            raise ValueError(
                "GDELT query cannot be blank."
            )

        if not 1 <= max_records <= 250:
            raise ValueError(
                "max_records must be between 1 and 250."
            )

        parameters = {
            "query": query.strip(),
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(max_records),
            "timespan": timespan,
            "sort": "datedesc",
        }

        return (
            self.endpoint
            + "?"
            + urlencode(parameters)
        )

    def search(
        self,
        query: str,
        *,
        max_records: int = 25,
        timespan: str = "7days",
    ) -> list[SearchResult]:
        url = self.build_url(
            query,
            max_records=max_records,
            timespan=timespan,
        )

        headers = {
            "User-Agent": (
                "EnergyMarketIntelligence/1.0 "
                "(research@example.invalid)"
            ),
            "Accept": "application/json",
        }

        body: bytes | None = None
        last_error: Exception | None = None

        for attempt in range(4):
            try:
                body = self.http_get(
                    url,
                    headers,
                    self.timeout_seconds,
                )
                last_error = None
                break

            except HTTPError as exc:
                last_error = exc

                if exc.code != 429:
                    break

                retry_after = exc.headers.get(
                    "Retry-After"
                )

                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        delay = 15.0
                else:
                    delay = min(
                        60.0,
                        (2 ** attempt) * 5.0
                        + random.uniform(0.0, 2.0),
                    )

                time.sleep(delay)

            except Exception as exc:
                last_error = exc
                break

        if body is None:
            if isinstance(last_error, HTTPError):
                if last_error.code == 429:
                    raise GdeltError(
                        "GDELT temporarily rate-limited "
                        "the request after retries."
                    ) from last_error

            raise GdeltError(
                f"GDELT search failed: {last_error}"
            ) from last_error

        try:
            payload = json.loads(
                body.decode(
                    "utf-8",
                    errors="replace",
                )
            )

        except Exception as exc:
            raise GdeltError(
                f"GDELT returned invalid JSON: {exc}"
            ) from exc

        articles = payload.get("articles", [])

        results: list[SearchResult] = []

        for article in articles:
            url_value = str(
                article.get("url", "")
            ).strip()

            title = str(
                article.get("title", "")
            ).strip()

            if not url_value or not title:
                continue

            results.append(
                SearchResult(
                    title=title,
                    url=url_value,
                    snippet=str(
                        article.get(
                            "seendate",
                            "",
                        )
                    ),
                    domain=str(
                        article.get(
                            "domain",
                            "",
                        )
                    ),
                    published_at=(
                        str(
                            article.get(
                                "seendate",
                                "",
                            )
                        ).strip()
                        or None
                    ),
                    metadata={
                        "language": article.get(
                            "language"
                        ),
                        "sourcecountry": article.get(
                            "sourcecountry"
                        ),
                    },
                )
            )

        return results
