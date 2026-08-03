from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import json
import re
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (
    Request,
    build_opener,
)


from market_intelligence.connectors.catalog import (
    ProviderSpec,
)
from market_intelligence.retrieval.exceptions import (
    SourceRateLimitedError,
    SourceResponseError,
    SourceUnauthorizedError,
    SourceUnavailableError,
)
from market_intelligence.retrieval.models import (
    RetrievedRecord,
    RetrievalMethod,
)


DEFAULT_MAX_BYTES = 5_000_000


@dataclass(frozen=True)
class WebFetchResponse:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    headers: dict[str, str]


HttpFetch = Callable[
    [str, dict[str, str], int],
    WebFetchResponse,
]


class _ReadableHtmlParser(HTMLParser):
    BLOCKED_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "template",
    }

    TEXT_TAGS = {
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "td",
        "th",
        "caption",
        "article",
        "section",
        "main",
        "time",
        "title",
    }

    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True
        )
        self._blocked_depth = 0
        self._current_tag: str | None = None
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ) -> None:
        normalized = tag.lower()

        if normalized in self.BLOCKED_TAGS:
            self._blocked_depth += 1

        self._current_tag = normalized

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        normalized = tag.lower()

        if (
            normalized in self.BLOCKED_TAGS
            and self._blocked_depth > 0
        ):
            self._blocked_depth -= 1

        self._current_tag = None

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._blocked_depth:
            return

        cleaned = re.sub(
            r"\s+",
            " ",
            unescape(data),
        ).strip()

        if not cleaned:
            return

        if self._current_tag == "title":
            self._title_parts.append(cleaned)

        if (
            self._current_tag in self.TEXT_TAGS
            or len(cleaned) >= 40
        ):
            self._text_parts.append(cleaned)

    @property
    def title(self) -> str:
        return " ".join(
            self._title_parts
        ).strip()

    @property
    def text(self) -> str:
        combined = "\n".join(
            self._text_parts
        )

        return re.sub(
            r"\n{3,}",
            "\n\n",
            combined,
        ).strip()


def _default_http_fetch(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> WebFetchResponse:
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
                DEFAULT_MAX_BYTES + 1
            )

            return WebFetchResponse(
                requested_url=url,
                final_url=response.geturl(),
                status_code=int(
                    response.getcode()
                ),
                content_type=(
                    response.headers.get(
                        "Content-Type",
                        "",
                    )
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
                f"HTTP {exc.code}: access denied."
            ) from exc

        if exc.code == 429:
            raise SourceRateLimitedError(
                "HTTP 429: source rate limit reached."
            ) from exc

        if exc.code >= 500:
            raise SourceUnavailableError(
                f"HTTP {exc.code}: source unavailable."
            ) from exc

        raise SourceResponseError(
            f"HTTP {exc.code}: unusable response."
        ) from exc

    except URLError as exc:
        raise SourceUnavailableError(
            f"Network failure: {exc.reason}"
        ) from exc


def _normalized_hostname(
    value: str,
) -> str:
    parsed = urlparse(value)
    hostname = (
        parsed.hostname
        or value
    ).lower().strip(".")

    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname


def _domain_allowed(
    url: str,
    allowed_domains: tuple[str, ...],
) -> bool:
    hostname = _normalized_hostname(url)

    return any(
        hostname == domain.lower()
        or hostname.endswith(
            f".{domain.lower()}"
        )
        for domain in allowed_domains
    )


def _extract_json_text(
    body: bytes,
) -> tuple[str, str]:
    try:
        payload = json.loads(
            body.decode("utf-8")
        )
    except Exception as exc:
        raise SourceResponseError(
            "The source returned invalid JSON."
        ) from exc

    formatted = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )

    return "Structured official response", formatted


def _extract_html_text(
    body: bytes,
) -> tuple[str, str]:
    try:
        decoded = body.decode(
            "utf-8",
            errors="replace",
        )
    except Exception as exc:
        raise SourceResponseError(
            "The HTML response could not be decoded."
        ) from exc

    parser = _ReadableHtmlParser()
    parser.feed(decoded)

    title = (
        parser.title
        or "Official source"
    )

    text = parser.text

    if len(text) < 40:
        raise SourceResponseError(
            "The official page contained insufficient "
            "readable text."
        )

    return title, text


class OfficialWebConnector:
    connector_id = "official_web"

    def __init__(
        self,
        *,
        http_fetch: HttpFetch | None = None,
        timeout_seconds: int = 30,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self.http_fetch = (
            http_fetch
            or _default_http_fetch
        )
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def fetch(
        self,
        *,
        provider: ProviderSpec,
        url: str,
    ) -> RetrievedRecord:
        if not _domain_allowed(
            url,
            provider.domains,
        ):
            raise SourceUnauthorizedError(
                "Requested URL is outside the provider's "
                "approved domain list."
            )

        response = self.http_fetch(
            url,
            {
                "Accept": (
                    "text/html,application/json,"
                    "application/xhtml+xml;q=0.9,*/*;q=0.5"
                ),
                "User-Agent": (
                    "Energy-Market-Intelligence-Agent/0.1 "
                    "(research; source-attributed)"
                ),
            },
            self.timeout_seconds,
        )

        if response.status_code in {401, 403}:
            raise SourceUnauthorizedError(
                f"HTTP {response.status_code}: access denied."
            )

        if response.status_code == 429:
            raise SourceRateLimitedError(
                "HTTP 429: source rate limit reached."
            )

        if response.status_code >= 500:
            raise SourceUnavailableError(
                f"HTTP {response.status_code}: "
                "source unavailable."
            )

        if not 200 <= response.status_code < 300:
            raise SourceResponseError(
                f"HTTP {response.status_code}: "
                "unexpected status."
            )

        if not _domain_allowed(
            response.final_url,
            provider.domains,
        ):
            raise SourceUnauthorizedError(
                "The source redirected outside the provider's "
                "approved domains."
            )

        if len(response.body) > self.max_bytes:
            raise SourceResponseError(
                "The source response exceeded the configured "
                "maximum size."
            )

        content_type = (
            response.content_type
            .split(";", 1)[0]
            .strip()
            .lower()
        )

        if content_type in {
            "application/json",
            "application/ld+json",
        }:
            title, text = _extract_json_text(
                response.body
            )

        elif content_type in {
            "text/html",
            "application/xhtml+xml",
            "text/plain",
            "",
        }:
            title, text = _extract_html_text(
                response.body
            )

        else:
            raise SourceResponseError(
                f"Unsupported content type: "
                f"{content_type or 'unknown'}."
            )

        retrieved_at = datetime.now(
            timezone.utc
        )

        return RetrievedRecord(
            provider_id=provider.provider_id,
            method=RetrievalMethod.OFFICIAL_WEB,
            source_title=title,
            source_url=response.final_url,
            observed_at=None,
            published_at=None,
            retrieved_at=retrieved_at,
            payload={
                "title": title,
                "text": text,
                "raw_html": (
                    response.body.decode(
                        "utf-8",
                        errors="replace",
                    )
                    if content_type in {
                        "text/html",
                        "application/xhtml+xml",
                    }
                    else None
                ),
                "requested_url": response.requested_url,
                "final_url": response.final_url,
                "content_type": content_type,
                "status_code": response.status_code,
            },
            is_primary=provider.is_primary,
            authority_rank=provider.authority_rank,
            metadata={
                "approved_domain": True,
                "response_bytes": len(response.body),
                "has_unit": False,
                "has_market_context": False,
                "has_timezone": False,
                "complete_coverage": False,
            },
        )
