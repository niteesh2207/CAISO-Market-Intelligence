from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


EIA_API_BASE_URL = "https://api.eia.gov/v2"


class EiaConnectorError(RuntimeError):
    """Base exception for EIA connector failures."""


class EiaConfigurationError(EiaConnectorError):
    """Raised when required EIA configuration is unavailable."""


class EiaRequestError(EiaConnectorError):
    """Raised when an EIA HTTP request fails."""


class EiaResponseError(EiaConnectorError):
    """Raised when an EIA response does not match the expected contract."""


@dataclass(frozen=True)
class EiaQuery:
    route: str
    data: tuple[str, ...] = ()
    facets: dict[str, tuple[str, ...]] = field(default_factory=dict)
    start: str | None = None
    end: str | None = None
    frequency: str | None = None
    sort_column: str | None = None
    sort_direction: str = "asc"
    offset: int = 0
    length: int = 5000

    def normalized_route(self) -> str:
        route = self.route.strip().strip("/")

        if not route:
            raise ValueError("EIA route cannot be empty.")

        return route


@dataclass(frozen=True)
class EiaResult:
    route: str
    rows: tuple[dict[str, Any], ...]
    total: int | None
    frequency: str | None
    description: str | None
    retrieved_at: datetime
    request_url: str
    warnings: tuple[str, ...] = ()


HttpGet = Callable[
    [str, dict[str, str]],
    dict[str, Any],
]


def _default_http_get(
    url: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    request = Request(
        url,
        headers=headers,
        method="GET",
    )

    try:
        with urlopen(
            request,
            timeout=30,
        ) as response:
            payload = response.read()
    except Exception as exc:
        raise EiaRequestError(
            f"EIA request failed: {type(exc).__name__}: {exc}"
        ) from exc

    try:
        decoded = json.loads(
            payload.decode("utf-8")
        )
    except Exception as exc:
        raise EiaResponseError(
            "EIA returned a non-JSON response."
        ) from exc

    if not isinstance(decoded, dict):
        raise EiaResponseError(
            "EIA response root must be a JSON object."
        )

    return decoded


class EiaConnector:
    connector_id = "eia_api"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        http_get: HttpGet | None = None,
        base_url: str = EIA_API_BASE_URL,
    ) -> None:
        if api_key is None:
            resolved_api_key = (
                os.getenv("EIA_API_KEY")
                or ""
            )
        else:
            # An explicitly supplied empty string must remain empty.
            # This makes configuration behavior deterministic and
            # allows tests and callers to disable environment fallback.
            resolved_api_key = api_key

        self.api_key = resolved_api_key.strip()

        self.http_get = (
            http_get
            or _default_http_get
        )

        self.base_url = base_url.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def build_url(
        self,
        query: EiaQuery,
        *,
        require_api_key: bool = True,
    ) -> str:
        if require_api_key and not self.api_key:
            raise EiaConfigurationError(
                "EIA_API_KEY is not configured. "
                "Register for an official EIA API key and set "
                "the EIA_API_KEY environment variable."
            )

        parameters: list[
            tuple[str, str]
        ] = []

        if self.api_key:
            parameters.append(
                ("api_key", self.api_key)
            )

        if query.frequency:
            parameters.append(
                ("frequency", query.frequency)
            )

        for column in query.data:
            parameters.append(
                ("data[]", column)
            )

        for facet_name, values in query.facets.items():
            for value in values:
                parameters.append(
                    (
                        f"facets[{facet_name}][]",
                        value,
                    )
                )

        if query.start:
            parameters.append(
                ("start", query.start)
            )

        if query.end:
            parameters.append(
                ("end", query.end)
            )

        if query.sort_column:
            parameters.extend(
                (
                    (
                        "sort[0][column]",
                        query.sort_column,
                    ),
                    (
                        "sort[0][direction]",
                        query.sort_direction,
                    ),
                )
            )

        parameters.extend(
            (
                ("offset", str(query.offset)),
                ("length", str(query.length)),
            )
        )

        route = query.normalized_route()

        return (
            f"{self.base_url}/{route}/?"
            f"{urlencode(parameters)}"
        )

    def fetch(
        self,
        query: EiaQuery,
    ) -> EiaResult:
        url = self.build_url(query)

        payload = self.http_get(
            url,
            {
                "Accept": "application/json",
                "User-Agent": (
                    "Energy-Market-Intelligence-Agent/0.1"
                ),
            },
        )

        response = payload.get("response")

        if not isinstance(response, dict):
            error = payload.get("error")

            if error:
                raise EiaResponseError(
                    f"EIA API error: {error}"
                )

            raise EiaResponseError(
                "EIA response is missing the 'response' object."
            )

        raw_rows = response.get("data", [])

        if raw_rows is None:
            raw_rows = []

        if not isinstance(raw_rows, list):
            raise EiaResponseError(
                "EIA response.data must be a list."
            )

        rows: list[dict[str, Any]] = []

        for row in raw_rows:
            if not isinstance(row, dict):
                raise EiaResponseError(
                    "Every EIA data row must be an object."
                )

            rows.append(dict(row))

        total_raw = response.get("total")
        total: int | None = None

        if total_raw is not None:
            try:
                total = int(total_raw)
            except (TypeError, ValueError):
                total = None

        warnings: list[str] = []

        if total is not None and total > len(rows):
            warnings.append(
                "The EIA query returned a partial page. "
                "Pagination is required for the full result."
            )

        return EiaResult(
            route=query.normalized_route(),
            rows=tuple(rows),
            total=total,
            frequency=response.get("frequency"),
            description=response.get("description"),
            retrieved_at=datetime.now(timezone.utc),
            request_url=url,
            warnings=tuple(warnings),
        )

    def metadata(
        self,
        route: str = "",
    ) -> dict[str, Any]:
        if not self.api_key:
            raise EiaConfigurationError(
                "EIA_API_KEY is required for EIA API metadata "
                "and data requests."
            )

        normalized = route.strip().strip("/")

        url = (
            f"{self.base_url}/"
            if not normalized
            else f"{self.base_url}/{normalized}/"
        )

        url = (
            f"{url}?{urlencode({'api_key': self.api_key})}"
        )

        payload = self.http_get(
            url,
            {
                "Accept": "application/json",
                "User-Agent": (
                    "Energy-Market-Intelligence-Agent/0.1"
                ),
            },
        )

        if not isinstance(payload, dict):
            raise EiaResponseError(
                "EIA metadata response must be an object."
            )

        return payload

    def health(self) -> dict[str, Any]:
        return {
            "connector": self.connector_id,
            "configured": self.configured,
            "base_url": self.base_url,
            "api_version": "v2",
        }
