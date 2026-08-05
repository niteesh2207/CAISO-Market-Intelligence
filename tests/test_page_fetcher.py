import socket

import pytest

from market_intelligence.research.page_fetcher import (
    PageFetchError,
    _ReadableHtmlParser,
    _assert_public_http_url,
)


def public_dns(_hostname):
    return (
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("8.8.8.8", 0),
        ),
    )


def private_dns(_hostname):
    return (
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("127.0.0.1", 0),
        ),
    )


def test_html_parser_extracts_readable_text():
    parser = _ReadableHtmlParser()

    parser.feed(
        """
        <html>
          <head>
            <title>CAISO Update</title>
            <style>hidden css</style>
          </head>
          <body>
            <main>
              <h1>Grid conditions</h1>
              <p>Demand increased during the evening.</p>
              <script>hidden code</script>
            </main>
          </body>
        </html>
        """
    )

    assert parser.title == "CAISO Update"
    assert "Grid conditions" in parser.text
    assert "Demand increased" in parser.text
    assert "hidden css" not in parser.text
    assert "hidden code" not in parser.text


def test_rejects_localhost():
    with pytest.raises(
        PageFetchError,
        match="Localhost",
    ):
        _assert_public_http_url(
            "http://localhost:8000/test"
        )


def test_rejects_private_address():
    with pytest.raises(
        PageFetchError,
        match="non-public",
    ):
        _assert_public_http_url(
            "https://example.com/test",
            dns_resolver=private_dns,
        )


def test_accepts_public_address():
    _assert_public_http_url(
        "https://example.com/test",
        dns_resolver=public_dns,
    )


def test_rejects_non_http_scheme():
    with pytest.raises(
        PageFetchError,
        match="HTTP and HTTPS",
    ):
        _assert_public_http_url(
            "file:///windows/system.ini"
        )
