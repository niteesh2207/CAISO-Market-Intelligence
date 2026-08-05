from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin, urlparse
from urllib.request import (
    Request,
    build_opener,
)
from urllib.robotparser import RobotFileParser


class PageFetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchedPage:
    requested_url: str
    final_url: str
    title: str
    text: str
    content_type: str
    retrieved_at: str
    response_bytes: int


class _ReadableHtmlParser(HTMLParser):
    _BLOCKED = {
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "template",
    }

    _BREAK_TAGS = {
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "p",
        "section",
        "table",
        "td",
        "th",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True
        )
        self._blocked_depth = 0
        self._parts: list[str] = []
        self.title_parts: list[str] = []
        self._inside_title = False

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ) -> None:
        normalized = tag.lower()

        if normalized in self._BLOCKED:
            self._blocked_depth += 1
            return

        if normalized == "title":
            self._inside_title = True

        if (
            not self._blocked_depth
            and normalized in self._BREAK_TAGS
        ):
            self._parts.append("\n")

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        normalized = tag.lower()

        if normalized in self._BLOCKED:
            self._blocked_depth = max(
                0,
                self._blocked_depth - 1,
            )
            return

        if normalized == "title":
            self._inside_title = False

        if (
            not self._blocked_depth
            and normalized in self._BREAK_TAGS
        ):
            self._parts.append("\n")

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._blocked_depth:
            return

        cleaned = data.strip()

        if not cleaned:
            return

        if self._inside_title:
            self.title_parts.append(cleaned)

        self._parts.append(cleaned)
        self._parts.append(" ")

    @property
    def text(self) -> str:
        joined = unescape(
            "".join(self._parts)
        )

        joined = re.sub(
            r"[ \t]+",
            " ",
            joined,
        )

        joined = re.sub(
            r"\n\s*\n+",
            "\n",
            joined,
        )

        return joined.strip()

    @property
    def title(self) -> str:
        return " ".join(
            self.title_parts
        ).strip()


DnsResolver = Callable[[str], tuple]


def _resolve_hostname(
    hostname: str,
) -> tuple:
    return socket.getaddrinfo(
        hostname,
        None,
    )


def _assert_public_http_url(
    url: str,
    *,
    dns_resolver: DnsResolver = _resolve_hostname,
) -> None:
    parsed = urlparse(url)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        raise PageFetchError(
            "Only HTTP and HTTPS URLs are allowed."
        )

    if not parsed.hostname:
        raise PageFetchError(
            "URL hostname is missing."
        )

    hostname = parsed.hostname.lower()

    if hostname in {
        "localhost",
        "localhost.localdomain",
    }:
        raise PageFetchError(
            "Localhost URLs are not allowed."
        )

    try:
        addresses = {
            result[4][0]
            for result in dns_resolver(hostname)
        }
    except Exception as exc:
        raise PageFetchError(
            f"DNS resolution failed: {exc}"
        ) from exc

    if not addresses:
        raise PageFetchError(
            "Hostname resolved to no addresses."
        )

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise PageFetchError(
                "URL resolved to a non-public address."
            )


@dataclass
class PageFetcher:
    user_agent: str = (
        "EnergyMarketIntelligence/1.0 "
        "(trust-first research agent)"
    )
    timeout_seconds: float = 25.0
    maximum_bytes: int = 2_000_000
    maximum_text_characters: int = 30_000
    respect_robots_txt: bool = True

    def _robots_allowed(
        self,
        url: str,
    ) -> bool:
        if not self.respect_robots_txt:
            return True

        parsed = urlparse(url)

        robots_url = urljoin(
            f"{parsed.scheme}://{parsed.netloc}",
            "/robots.txt",
        )

        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            parser.read()
        except Exception:
            # Fail open for unreachable robots.txt,
            # while all other URL controls remain active.
            return True

        return parser.can_fetch(
            self.user_agent,
            url,
        )

    def fetch(
        self,
        url: str,
    ) -> FetchedPage:
        _assert_public_http_url(url)

        if not self._robots_allowed(url):
            raise PageFetchError(
                "Fetching is disallowed by robots.txt."
            )

        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": (
                    "text/html,"
                    "application/xhtml+xml,"
                    "text/plain;q=0.9,"
                    "*/*;q=0.1"
                ),
                "Accept-Language": "en-US,en;q=0.8",
            },
            method="GET",
        )

        opener = build_opener()

        try:
            with opener.open(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                final_url = response.geturl()
                _assert_public_http_url(final_url)

                content_type = (
                    response.headers.get_content_type()
                    or ""
                ).lower()

                charset = (
                    response.headers.get_content_charset()
                    or "utf-8"
                )

                body = response.read(
                    self.maximum_bytes + 1
                )

        except PageFetchError:
            raise

        except Exception as exc:
            raise PageFetchError(
                f"Page retrieval failed: {exc}"
            ) from exc

        if len(body) > self.maximum_bytes:
            raise PageFetchError(
                "Page exceeded the configured size limit."
            )

        if content_type not in {
            "text/html",
            "application/xhtml+xml",
            "text/plain",
        }:
            raise PageFetchError(
                "Unsupported content type: "
                + content_type
            )

        decoded = body.decode(
            charset,
            errors="replace",
        )

        if content_type == "text/plain":
            title = ""
            text = decoded.strip()
        else:
            parser = _ReadableHtmlParser()

            try:
                parser.feed(decoded)
                parser.close()
            except Exception as exc:
                raise PageFetchError(
                    f"HTML extraction failed: {exc}"
                ) from exc

            title = parser.title
            text = parser.text

        text = text[
            : self.maximum_text_characters
        ].strip()

        if len(text) < 80:
            raise PageFetchError(
                "Page contained insufficient readable text."
            )

        return FetchedPage(
            requested_url=url,
            final_url=final_url,
            title=title,
            text=text,
            content_type=content_type,
            retrieved_at=datetime.now(
                timezone.utc
            ).isoformat(),
            response_bytes=len(body),
        )
