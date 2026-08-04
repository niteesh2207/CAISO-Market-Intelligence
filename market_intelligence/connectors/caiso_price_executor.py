from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import re
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (
    Request,
    build_opener,
)
from zipfile import BadZipFile, ZipFile


from market_intelligence.connectors.caiso_price_query import (
    CaisoPriceQuery,
)
from market_intelligence.connectors.caiso_price_response import (
    CaisoPriceSummary,
    MAX_ARCHIVE_BYTES,
    parse_oasis_price_archive,
    summary_to_retrieved_record,
)
from market_intelligence.retrieval.exceptions import (
    SourceRateLimitedError,
    SourceResponseError,
    SourceUnauthorizedError,
    SourceUnavailableError,
)
from market_intelligence.retrieval.models import (
    RetrievedRecord,
)


ALLOWED_OASIS_DOMAINS = (
    "oasis.caiso.com",
    "oasis.prod.caiso.com",
)

DEFAULT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class OasisDownloadResponse:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    headers: dict[str, str]


OasisHttpGet = Callable[
    [str, dict[str, str], int],
    OasisDownloadResponse,
]


def _normalized_hostname(
    url: str,
) -> str:
    hostname = (
        urlparse(url).hostname
        or ""
    ).lower().strip(".")

    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname


def _approved_oasis_url(
    url: str,
) -> bool:
    parsed = urlparse(url)

    if parsed.scheme.lower() != "https":
        return False

    hostname = _normalized_hostname(url)

    return any(
        hostname == domain
        or hostname.endswith(f".{domain}")
        for domain in ALLOWED_OASIS_DOMAINS
    )


def _default_http_get(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> OasisDownloadResponse:
    request = Request(
        url,
        headers=headers,
        method="GET",
    )

    opener = build_opener()

    try:
        with opener.open(
            request,
            timeout=timeout_seconds,
        ) as response:
            body = response.read(
                MAX_ARCHIVE_BYTES + 1
            )

            return OasisDownloadResponse(
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
                f"CAISO OASIS returned HTTP {exc.code}."
            ) from exc

        if exc.code == 429:
            raise SourceRateLimitedError(
                "CAISO OASIS rate limit reached."
            ) from exc

        if exc.code >= 500:
            raise SourceUnavailableError(
                f"CAISO OASIS returned HTTP {exc.code}."
            ) from exc

        raise SourceResponseError(
            f"CAISO OASIS returned HTTP {exc.code}."
        ) from exc

    except URLError as exc:
        raise SourceUnavailableError(
            f"CAISO OASIS network failure: {exc.reason}"
        ) from exc


def _decode_possible_error(
    body: bytes,
) -> str:
    for encoding in (
        "utf-8-sig",
        "utf-8",
        "windows-1252",
    ):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue

    return ""


def _extract_xml_error(
    body: bytes,
) -> str | None:
    candidates: list[str] = []

    try:
        with ZipFile(BytesIO(body)) as archive:
            for info in archive.infolist():
                if (
                    not info.is_dir()
                    and info.filename.lower().endswith(".xml")
                ):
                    candidates.append(
                        _decode_possible_error(
                            archive.read(info)
                        )
                    )
    except BadZipFile:
        candidates.append(
            _decode_possible_error(body)
        )

    for text in candidates:
        if not text:
            continue

        message_match = re.search(
            r"<(?:ERR_DESC|ERROR_DESC|MESSAGE)>"
            r"\s*(.*?)\s*"
            r"</(?:ERR_DESC|ERROR_DESC|MESSAGE)>",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if message_match:
            return re.sub(
                r"\s+",
                " ",
                message_match.group(1),
            ).strip()

        if re.search(
            r"<(?:ERROR|ERR_CODE|ERR_DESC)\b",
            text,
            flags=re.IGNORECASE,
        ):
            cleaned = re.sub(
                r"<[^>]+>",
                " ",
                text,
            )

            return re.sub(
                r"\s+",
                " ",
                cleaned,
            ).strip()[:500]

    return None


class CaisoOasisPriceExecutor:
    connector_id = "caiso_oasis"

    def __init__(
        self,
        *,
        http_get: OasisHttpGet | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.http_get = (
            http_get
            or _default_http_get
        )
        self.timeout_seconds = timeout_seconds

    def download(
        self,
        query: CaisoPriceQuery,
    ) -> OasisDownloadResponse:
        if not _approved_oasis_url(
            query.url
        ):
            raise SourceUnauthorizedError(
                "CAISO OASIS query URL is outside "
                "the approved HTTPS domains."
            )

        response = self.http_get(
            query.url,
            {
                "Accept": (
                    "application/zip,"
                    "application/octet-stream,"
                    "text/csv;q=0.9,*/*;q=0.5"
                ),
                "User-Agent": (
                    "CAISO-Market-Intelligence/0.1 "
                    "(source-attributed market research)"
                ),
            },
            self.timeout_seconds,
        )

        if response.status_code in {401, 403}:
            raise SourceUnauthorizedError(
                f"CAISO OASIS returned HTTP "
                f"{response.status_code}."
            )

        if response.status_code == 429:
            raise SourceRateLimitedError(
                "CAISO OASIS rate limit reached."
            )

        if response.status_code >= 500:
            raise SourceUnavailableError(
                f"CAISO OASIS returned HTTP "
                f"{response.status_code}."
            )

        if not 200 <= response.status_code < 300:
            raise SourceResponseError(
                f"Unexpected CAISO OASIS HTTP status "
                f"{response.status_code}."
            )

        if not _approved_oasis_url(
            response.final_url
        ):
            raise SourceUnauthorizedError(
                "CAISO OASIS redirected outside "
                "the approved HTTPS domains."
            )

        if not response.body:
            raise SourceResponseError(
                "CAISO OASIS returned an empty response."
            )

        if len(response.body) > MAX_ARCHIVE_BYTES:
            raise SourceResponseError(
                "CAISO OASIS response exceeded "
                "the configured size limit."
            )

        oasis_error = _extract_xml_error(
            response.body
        )

        if oasis_error:
            raise SourceResponseError(
                f"CAISO OASIS rejected the query: "
                f"{oasis_error}"
            )

        return response

    def execute(
        self,
        query: CaisoPriceQuery,
        *,
        require_complete_coverage: bool = True,
    ) -> CaisoPriceSummary:
        response = self.download(query)

        return parse_oasis_price_archive(
            response.body,
            query=query,
            require_complete_coverage=(
                require_complete_coverage
            ),
        )

    def execute_to_record(
        self,
        query: CaisoPriceQuery,
        *,
        require_complete_coverage: bool = True,
    ) -> RetrievedRecord:
        response = self.download(query)

        summary = parse_oasis_price_archive(
            response.body,
            query=query,
            require_complete_coverage=(
                require_complete_coverage
            ),
        )

        return summary_to_retrieved_record(
            summary,
            source_url=response.final_url,
            retrieved_at=datetime.now(
                timezone.utc
            ),
        )
