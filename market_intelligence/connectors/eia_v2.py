from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


from market_intelligence.retrieval.exceptions import (
    SourceRateLimitedError,
    SourceResponseError,
    SourceUnauthorizedError,
    SourceUnavailableError,
)


EIA_API_ROOT = "https://api.eia.gov/v2"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_PAGE_LENGTH = 5000
MAX_RESPONSE_BYTES = 25_000_000


class EiaConfigurationError(ValueError):
    """EIA client configuration is incomplete."""


class EiaRouteValidationError(ValueError):
    """An EIA route or parameter failed metadata validation."""


@dataclass(frozen=True)
class EiaHttpResponse:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    headers: dict[str, str]


EiaHttpGet = Callable[
    [str, dict[str, str], int],
    EiaHttpResponse,
]


@dataclass(frozen=True)
class EiaFrequency:
    id: str
    description: str | None = None


@dataclass(frozen=True)
class EiaFacet:
    id: str
    description: str | None = None


@dataclass(frozen=True)
class EiaDataColumn:
    id: str
    description: str | None = None
    unit: str | None = None


@dataclass(frozen=True)
class EiaRouteMetadata:
    route: str
    id: str | None
    name: str | None
    description: str | None
    frequencies: tuple[EiaFrequency, ...]
    facets: tuple[EiaFacet, ...]
    data_columns: tuple[EiaDataColumn, ...]
    child_routes: tuple[str, ...]
    raw: dict[str, Any]

    @property
    def frequency_ids(self) -> frozenset[str]:
        return frozenset(
            frequency.id
            for frequency in self.frequencies
        )

    @property
    def facet_ids(self) -> frozenset[str]:
        return frozenset(
            facet.id
            for facet in self.facets
        )

    @property
    def data_column_ids(self) -> frozenset[str]:
        return frozenset(
            column.id
            for column in self.data_columns
        )


@dataclass(frozen=True)
class EiaDataRequest:
    route: str
    frequency: str
    data_columns: tuple[str, ...]
    facets: tuple[tuple[str, tuple[str, ...]], ...] = ()
    start: str | None = None
    end: str | None = None
    sort: tuple[tuple[str, str], ...] = ()
    offset: int = 0
    length: int = DEFAULT_PAGE_LENGTH


@dataclass(frozen=True)
class EiaDataResult:
    request: EiaDataRequest
    rows: tuple[dict[str, Any], ...]
    total: int
    retrieved_at: datetime
    source_url: str
    raw_response: dict[str, Any]

    @property
    def complete_page(self) -> bool:
        return (
            self.request.offset + len(self.rows)
            >= self.total
        )


def normalize_eia_route(route: str) -> str:
    cleaned = route.strip().strip("/")

    if cleaned.startswith("v2/"):
        cleaned = cleaned[3:]

    if not cleaned:
        raise EiaRouteValidationError(
            "EIA route cannot be empty."
        )

    segments = cleaned.split("/")

    if any(
        not segment
        or segment in {".", ".."}
        for segment in segments
    ):
        raise EiaRouteValidationError(
            "EIA route contains an invalid segment."
        )

    return "/".join(segments)


def _approved_eia_url(url: str) -> bool:
    parsed = urlparse(url)

    return (
        parsed.scheme.lower() == "https"
        and (parsed.hostname or "").lower()
        == "api.eia.gov"
    )


def _default_http_get(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> EiaHttpResponse:
    request = Request(
        url,
        headers=headers,
        method="GET",
    )

    try:
        with urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            body = response.read(
                MAX_RESPONSE_BYTES + 1
            )

            return EiaHttpResponse(
                requested_url=url,
                final_url=response.geturl(),
                status_code=int(response.getcode()),
                content_type=response.headers.get(
                    "Content-Type",
                    "",
                ),
                body=body,
                headers={
                    key.lower(): value
                    for key, value
                    in response.headers.items()
                },
            )

    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise SourceUnauthorizedError(
                f"EIA returned HTTP {exc.code}."
            ) from exc

        if exc.code == 429:
            raise SourceRateLimitedError(
                "EIA API rate limit reached."
            ) from exc

        if exc.code >= 500:
            raise SourceUnavailableError(
                f"EIA returned HTTP {exc.code}."
            ) from exc

        raise SourceResponseError(
            f"EIA returned HTTP {exc.code}."
        ) from exc

    except URLError as exc:
        raise SourceUnavailableError(
            f"EIA network failure: {exc.reason}"
        ) from exc


def _json_body(
    response: EiaHttpResponse,
) -> dict[str, Any]:
    if not response.body:
        raise SourceResponseError(
            "EIA returned an empty response."
        )

    if len(response.body) > MAX_RESPONSE_BYTES:
        raise SourceResponseError(
            "EIA response exceeded the configured size limit."
        )

    if not _approved_eia_url(response.final_url):
        raise SourceUnauthorizedError(
            "EIA redirected outside api.eia.gov."
        )

    try:
        payload = json.loads(
            response.body.decode("utf-8-sig")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise SourceResponseError(
            "EIA response was not valid UTF-8 JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise SourceResponseError(
            "EIA response root must be a JSON object."
        )

    error = payload.get("error")

    if error:
        if isinstance(error, dict):
            message = (
                error.get("message")
                or error.get("code")
                or str(error)
            )
        else:
            message = str(error)

        raise SourceResponseError(
            f"EIA rejected the request: {message}"
        )

    return payload


def _items(
    value: Any,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    return [
        item
        for item in value
        if isinstance(item, dict)
    ]


def parse_eia_metadata(
    route: str,
    payload: dict[str, Any],
) -> EiaRouteMetadata:
    response = payload.get("response")

    if not isinstance(response, dict):
        raise SourceResponseError(
            "EIA metadata response is missing "
            "the 'response' object."
        )

    frequencies = tuple(
        EiaFrequency(
            id=str(item.get("id", "")).strip(),
            description=(
                str(item["description"]).strip()
                if item.get("description") is not None
                else None
            ),
        )
        for item in _items(
            response.get("frequency")
            or response.get("frequencies")
        )
        if str(item.get("id", "")).strip()
    )

    facets = tuple(
        EiaFacet(
            id=str(item.get("id", "")).strip(),
            description=(
                str(item["description"]).strip()
                if item.get("description") is not None
                else None
            ),
        )
        for item in _items(response.get("facets"))
        if str(item.get("id", "")).strip()
    )

    data_columns = tuple(
        EiaDataColumn(
            id=str(item.get("id", "")).strip(),
            description=(
                str(item["description"]).strip()
                if item.get("description") is not None
                else None
            ),
            unit=(
                str(item["unit"]).strip()
                if item.get("unit") is not None
                else None
            ),
        )
        for item in _items(response.get("data"))
        if str(item.get("id", "")).strip()
    )

    child_routes = tuple(
        str(item.get("id", "")).strip()
        for item in _items(response.get("routes"))
        if str(item.get("id", "")).strip()
    )

    return EiaRouteMetadata(
        route=normalize_eia_route(route),
        id=(
            str(response["id"]).strip()
            if response.get("id") is not None
            else None
        ),
        name=(
            str(response["name"]).strip()
            if response.get("name") is not None
            else None
        ),
        description=(
            str(response["description"]).strip()
            if response.get("description") is not None
            else None
        ),
        frequencies=frequencies,
        facets=facets,
        data_columns=data_columns,
        child_routes=child_routes,
        raw=payload,
    )


class EiaV2Client:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        http_get: EiaHttpGet | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        resolved_key = (
            api_key
            if api_key is not None
            else os.getenv("EIA_API_KEY", "")
        )

        self.api_key = resolved_key.strip()
        self.http_get = http_get or _default_http_get
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _require_key(self) -> None:
        if not self.configured:
            raise EiaConfigurationError(
                "EIA_API_KEY is required for EIA API calls."
            )

    def _get(
        self,
        url: str,
    ) -> tuple[dict[str, Any], str]:
        self._require_key()

        if not _approved_eia_url(url):
            raise SourceUnauthorizedError(
                "EIA request URL is outside "
                "the approved HTTPS API domain."
            )

        response = self.http_get(
            url,
            {
                "Accept": "application/json",
                "User-Agent": (
                    "CAISO-Market-Intelligence/0.1 "
                    "(source-attributed energy research)"
                ),
            },
            self.timeout_seconds,
        )

        if response.status_code in {401, 403}:
            raise SourceUnauthorizedError(
                f"EIA returned HTTP "
                f"{response.status_code}."
            )

        if response.status_code == 429:
            raise SourceRateLimitedError(
                "EIA API rate limit reached."
            )

        if response.status_code >= 500:
            raise SourceUnavailableError(
                f"EIA returned HTTP "
                f"{response.status_code}."
            )

        if not 200 <= response.status_code < 300:
            raise SourceResponseError(
                f"Unexpected EIA HTTP status "
                f"{response.status_code}."
            )

        return _json_body(response), response.final_url

    def metadata(
        self,
        route: str,
    ) -> EiaRouteMetadata:
        normalized = normalize_eia_route(route)

        url = (
            f"{EIA_API_ROOT}/"
            f"{'/'.join(quote(part) for part in normalized.split('/'))}/"
            f"?{urlencode({'api_key': self.api_key})}"
        )

        payload, _ = self._get(url)

        return parse_eia_metadata(
            normalized,
            payload,
        )

    def validate_request(
        self,
        request: EiaDataRequest,
        metadata: EiaRouteMetadata,
    ) -> None:
        route = normalize_eia_route(request.route)

        if route != metadata.route:
            raise EiaRouteValidationError(
                "EIA request route does not match "
                "the supplied metadata."
            )

        if (
            metadata.frequency_ids
            and request.frequency
            not in metadata.frequency_ids
        ):
            raise EiaRouteValidationError(
                f"Unsupported EIA frequency "
                f"{request.frequency!r}."
            )

        unknown_columns = (
            set(request.data_columns)
            - set(metadata.data_column_ids)
        )

        if unknown_columns:
            raise EiaRouteValidationError(
                "Unsupported EIA data columns: "
                + ", ".join(sorted(unknown_columns))
            )

        unknown_facets = (
            {
                facet_id
                for facet_id, _ in request.facets
            }
            - set(metadata.facet_ids)
        )

        if unknown_facets:
            raise EiaRouteValidationError(
                "Unsupported EIA facets: "
                + ", ".join(sorted(unknown_facets))
            )

        if request.offset < 0:
            raise EiaRouteValidationError(
                "EIA offset cannot be negative."
            )

        if not 1 <= request.length <= 5000:
            raise EiaRouteValidationError(
                "EIA page length must be between 1 and 5000."
            )

        for column, direction in request.sort:
            if direction.lower() not in {
                "asc",
                "desc",
            }:
                raise EiaRouteValidationError(
                    "EIA sort direction must be "
                    "'asc' or 'desc'."
                )

    def build_data_url(
        self,
        request: EiaDataRequest,
        *,
        metadata: EiaRouteMetadata,
    ) -> str:
        self._require_key()
        self.validate_request(
            request,
            metadata,
        )

        normalized = normalize_eia_route(
            request.route
        )

        parameters: list[tuple[str, str]] = [
            ("api_key", self.api_key),
            ("frequency", request.frequency),
            ("offset", str(request.offset)),
            ("length", str(request.length)),
        ]

        for column in request.data_columns:
            parameters.append(
                ("data[]", column)
            )

        for facet_id, values in request.facets:
            for value in values:
                parameters.append(
                    (f"facets[{facet_id}][]", value)
                )

        if request.start is not None:
            parameters.append(
                ("start", request.start)
            )

        if request.end is not None:
            parameters.append(
                ("end", request.end)
            )

        for index, (column, direction) in enumerate(
            request.sort
        ):
            parameters.extend(
                [
                    (
                        f"sort[{index}][column]",
                        column,
                    ),
                    (
                        f"sort[{index}][direction]",
                        direction.lower(),
                    ),
                ]
            )

        encoded_route = "/".join(
            quote(part)
            for part in normalized.split("/")
        )

        return (
            f"{EIA_API_ROOT}/{encoded_route}/data/"
            f"?{urlencode(parameters)}"
        )

    def data(
        self,
        request: EiaDataRequest,
        *,
        metadata: EiaRouteMetadata | None = None,
    ) -> EiaDataResult:
        resolved_metadata = (
            metadata
            if metadata is not None
            else self.metadata(request.route)
        )

        url = self.build_data_url(
            request,
            metadata=resolved_metadata,
        )

        payload, final_url = self._get(url)

        response = payload.get("response")

        if not isinstance(response, dict):
            raise SourceResponseError(
                "EIA data response is missing "
                "the 'response' object."
            )

        rows = response.get("data")

        if not isinstance(rows, list):
            raise SourceResponseError(
                "EIA data response is missing "
                "the data array."
            )

        normalized_rows = tuple(
            row
            for row in rows
            if isinstance(row, dict)
        )

        total_raw = response.get("total", len(normalized_rows))

        try:
            total = int(total_raw)
        except (TypeError, ValueError) as exc:
            raise SourceResponseError(
                "EIA response total is invalid."
            ) from exc

        return EiaDataResult(
            request=request,
            rows=normalized_rows,
            total=total,
            retrieved_at=datetime.now(timezone.utc),
            source_url=final_url,
            raw_response=payload,
        )

    def iter_all(
        self,
        request: EiaDataRequest,
        *,
        metadata: EiaRouteMetadata | None = None,
        maximum_rows: int = 100_000,
    ) -> Iterable[dict[str, Any]]:
        resolved_metadata = (
            metadata
            if metadata is not None
            else self.metadata(request.route)
        )

        offset = request.offset
        emitted = 0

        while True:
            page_request = EiaDataRequest(
                route=request.route,
                frequency=request.frequency,
                data_columns=request.data_columns,
                facets=request.facets,
                start=request.start,
                end=request.end,
                sort=request.sort,
                offset=offset,
                length=request.length,
            )

            result = self.data(
                page_request,
                metadata=resolved_metadata,
            )

            if not result.rows:
                break

            for row in result.rows:
                emitted += 1

                if emitted > maximum_rows:
                    raise SourceResponseError(
                        "EIA pagination exceeded "
                        "the configured row limit."
                    )

                yield row

            offset += len(result.rows)

            if offset >= result.total:
                break
