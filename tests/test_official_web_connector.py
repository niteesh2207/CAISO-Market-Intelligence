import pytest

from market_intelligence.connectors.catalog import (
    provider_by_id,
)
from market_intelligence.connectors.official_web import (
    OfficialWebConnector,
    WebFetchResponse,
)
from market_intelligence.retrieval.exceptions import (
    SourceResponseError,
    SourceUnauthorizedError,
)


def response(
    *,
    requested_url: str,
    final_url: str | None = None,
    status_code: int = 200,
    content_type: str = "text/html; charset=utf-8",
    body: bytes | None = None,
):
    return WebFetchResponse(
        requested_url=requested_url,
        final_url=final_url or requested_url,
        status_code=status_code,
        content_type=content_type,
        body=(
            body
            or (
                b"<html><head><title>Official report</title></head>"
                b"<body><main><h1>Market update</h1>"
                b"<p>This official report contains sufficient "
                b"readable information for the energy research "
                b"retrieval validation process.</p></main></body>"
                b"</html>"
            )
        ),
        headers={},
    )


def test_official_page_is_normalized():
    provider = provider_by_id(
        "ferc_elibrary"
    )
    assert provider is not None

    url = (
        "https://www.ferc.gov/"
        "official-market-document"
    )

    connector = OfficialWebConnector(
        http_fetch=lambda url, headers, timeout: response(
            requested_url=url
        )
    )

    record = connector.fetch(
        provider=provider,
        url=url,
    )

    assert record.provider_id == "ferc_elibrary"
    assert record.is_primary is True
    assert record.source_title == "Official report"
    assert "official report" in (
        record.payload["text"].lower()
    )


def test_unapproved_domain_is_rejected_before_fetch():
    provider = provider_by_id(
        "ferc_elibrary"
    )
    assert provider is not None

    called = False

    def fake_fetch(url, headers, timeout):
        nonlocal called
        called = True
        return response(requested_url=url)

    connector = OfficialWebConnector(
        http_fetch=fake_fetch
    )

    with pytest.raises(
        SourceUnauthorizedError,
        match="approved domain",
    ):
        connector.fetch(
            provider=provider,
            url="https://untrusted.example/report",
        )

    assert called is False


def test_licensed_provider_is_rejected_before_fetch():
    provider = provider_by_id("woodmac_optional")
    assert provider is not None

    called = False

    def fake_fetch(url, headers, timeout):
        nonlocal called
        called = True
        return response(requested_url=url)

    connector = OfficialWebConnector(http_fetch=fake_fetch)

    with pytest.raises(
        SourceUnauthorizedError,
        match="entitled server-side delivery",
    ):
        connector.fetch(
            provider=provider,
            url="https://www.woodmac.com/report",
        )

    assert called is False


def test_redirect_outside_approved_domain_is_rejected():
    provider = provider_by_id(
        "nrc_reactor_status"
    )
    assert provider is not None

    requested = (
        "https://www.nrc.gov/reactors/status"
    )

    connector = OfficialWebConnector(
        http_fetch=lambda url, headers, timeout: response(
            requested_url=requested,
            final_url=(
                "https://untrusted.example/copied-status"
            ),
        )
    )

    with pytest.raises(
        SourceUnauthorizedError,
        match="redirected outside",
    ):
        connector.fetch(
            provider=provider,
            url=requested,
        )


def test_empty_page_is_rejected():
    provider = provider_by_id(
        "nrc_reactor_status"
    )
    assert provider is not None

    url = "https://www.nrc.gov/empty"

    connector = OfficialWebConnector(
        http_fetch=lambda url, headers, timeout: response(
            requested_url=url,
            body=b"<html><body>Empty</body></html>",
        )
    )

    with pytest.raises(
        SourceResponseError,
        match="insufficient",
    ):
        connector.fetch(
            provider=provider,
            url=url,
        )


def test_json_response_is_supported():
    provider = provider_by_id("ercot")
    assert provider is not None

    url = "https://www.ercot.com/api/status"

    connector = OfficialWebConnector(
        http_fetch=lambda url, headers, timeout: response(
            requested_url=url,
            content_type="application/json",
            body=(
                b'{"status":"normal","reserve_mw":5000}'
            ),
        )
    )

    record = connector.fetch(
        provider=provider,
        url=url,
    )

    assert "reserve_mw" in record.payload["text"]
    assert (
        record.payload["content_type"]
        == "application/json"
    )


def test_oversized_response_is_rejected():
    provider = provider_by_id("ercot")
    assert provider is not None

    url = "https://www.ercot.com/large"

    connector = OfficialWebConnector(
        http_fetch=lambda url, headers, timeout: response(
            requested_url=url,
            body=b"x" * 101,
            content_type="text/plain",
        ),
        max_bytes=100,
    )

    with pytest.raises(
        SourceResponseError,
        match="maximum size",
    ):
        connector.fetch(
            provider=provider,
            url=url,
        )


def test_http_403_response_is_classified():
    provider = provider_by_id(
        "eia_api"
    )
    assert provider is not None

    url = "https://www.eia.gov/report"

    connector = OfficialWebConnector(
        http_fetch=lambda url, headers, timeout: response(
            requested_url=url,
            status_code=403,
        )
    )

    with pytest.raises(
        SourceUnauthorizedError,
        match="403",
    ):
        connector.fetch(
            provider=provider,
            url=url,
        )
