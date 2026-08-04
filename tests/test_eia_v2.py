import json
from urllib.parse import parse_qs, urlparse

import pytest

from market_intelligence.connectors.eia_v2 import (
    EiaConfigurationError,
    EiaDataRequest,
    EiaHttpResponse,
    EiaRouteValidationError,
    EiaV2Client,
    normalize_eia_route,
    parse_eia_metadata,
)
from market_intelligence.retrieval.exceptions import (
    SourceResponseError,
    SourceUnauthorizedError,
)


METADATA_PAYLOAD = {
    "response": {
        "id": "region-data",
        "name": "Hourly Demand",
        "description": "Demand and generation data",
        "frequency": [
            {
                "id": "hourly",
                "description": "Hourly UTC",
            }
        ],
        "facets": [
            {
                "id": "respondent",
                "description": "Balancing authority",
            },
            {
                "id": "type",
                "description": "Series type",
            },
        ],
        "data": [
            {
                "id": "value",
                "description": "Value",
                "unit": "megawatthours",
            }
        ],
        "routes": [],
    }
}


DATA_PAYLOAD = {
    "response": {
        "total": "2",
        "data": [
            {
                "period": "2026-08-03T12",
                "respondent": "CISO",
                "type": "D",
                "value": "42000",
                "value-units": "megawatthours",
            },
            {
                "period": "2026-08-03T13",
                "respondent": "CISO",
                "type": "D",
                "value": "43000",
                "value-units": "megawatthours",
            },
        ],
    }
}


def response(url, payload, status=200, final_url=None):
    return EiaHttpResponse(
        requested_url=url,
        final_url=final_url or url,
        status_code=status,
        content_type="application/json",
        body=json.dumps(payload).encode("utf-8"),
        headers={},
    )


def test_route_normalization():
    assert normalize_eia_route(
        "/v2/electricity/rto/region-data/"
    ) == "electricity/rto/region-data"


def test_invalid_route_segment_is_rejected():
    with pytest.raises(
        EiaRouteValidationError,
        match="invalid segment",
    ):
        normalize_eia_route(
            "electricity/../natural-gas"
        )


def test_metadata_is_parsed():
    metadata = parse_eia_metadata(
        "electricity/rto/region-data",
        METADATA_PAYLOAD,
    )

    assert metadata.id == "region-data"
    assert metadata.frequency_ids == {"hourly"}
    assert metadata.facet_ids == {
        "respondent",
        "type",
    }
    assert metadata.data_column_ids == {"value"}


def test_api_key_is_required():
    client = EiaV2Client(
        api_key="",
        http_get=lambda url, headers, timeout: response(
            url,
            METADATA_PAYLOAD,
        ),
    )

    with pytest.raises(
        EiaConfigurationError,
        match="EIA_API_KEY",
    ):
        client.metadata(
            "electricity/rto/region-data"
        )


def test_metadata_request_uses_https_and_api_domain():
    captured = {}

    def fake_get(url, headers, timeout):
        captured["url"] = url
        return response(
            url,
            METADATA_PAYLOAD,
        )

    client = EiaV2Client(
        api_key="test-key",
        http_get=fake_get,
    )

    metadata = client.metadata(
        "electricity/rto/region-data"
    )

    assert metadata.id == "region-data"
    assert captured["url"].startswith(
        "https://api.eia.gov/v2/"
    )
    assert "api_key=test-key" in captured["url"]


def test_request_is_validated_against_metadata():
    client = EiaV2Client(
        api_key="test-key"
    )

    metadata = parse_eia_metadata(
        "electricity/rto/region-data",
        METADATA_PAYLOAD,
    )

    with pytest.raises(
        EiaRouteValidationError,
        match="frequency",
    ):
        client.validate_request(
            EiaDataRequest(
                route="electricity/rto/region-data",
                frequency="monthly",
                data_columns=("value",),
            ),
            metadata,
        )


def test_unknown_data_column_is_rejected():
    client = EiaV2Client(
        api_key="test-key"
    )

    metadata = parse_eia_metadata(
        "electricity/rto/region-data",
        METADATA_PAYLOAD,
    )

    with pytest.raises(
        EiaRouteValidationError,
        match="data columns",
    ):
        client.validate_request(
            EiaDataRequest(
                route="electricity/rto/region-data",
                frequency="hourly",
                data_columns=("unknown",),
            ),
            metadata,
        )


def test_unknown_facet_is_rejected():
    client = EiaV2Client(
        api_key="test-key"
    )

    metadata = parse_eia_metadata(
        "electricity/rto/region-data",
        METADATA_PAYLOAD,
    )

    with pytest.raises(
        EiaRouteValidationError,
        match="facets",
    ):
        client.validate_request(
            EiaDataRequest(
                route="electricity/rto/region-data",
                frequency="hourly",
                data_columns=("value",),
                facets=(
                    ("unknown", ("x",)),
                ),
            ),
            metadata,
        )


def test_data_url_contains_arrays_and_facets():
    client = EiaV2Client(
        api_key="test-key"
    )

    metadata = parse_eia_metadata(
        "electricity/rto/region-data",
        METADATA_PAYLOAD,
    )

    request = EiaDataRequest(
        route="electricity/rto/region-data",
        frequency="hourly",
        data_columns=("value",),
        facets=(
            ("respondent", ("CISO",)),
            ("type", ("D",)),
        ),
        start="2026-08-03T12",
        end="2026-08-03T13",
        sort=(("period", "asc"),),
    )

    url = client.build_data_url(
        request,
        metadata=metadata,
    )

    parsed = parse_qs(
        urlparse(url).query
    )

    assert parsed["data[]"] == ["value"]
    assert parsed["facets[respondent][]"] == [
        "CISO"
    ]
    assert parsed["facets[type][]"] == ["D"]
    assert parsed["frequency"] == ["hourly"]


def test_data_rows_are_returned():
    calls = []

    def fake_get(url, headers, timeout):
        calls.append(url)

        if "/data/" in url:
            return response(
                url,
                DATA_PAYLOAD,
            )

        return response(
            url,
            METADATA_PAYLOAD,
        )

    client = EiaV2Client(
        api_key="test-key",
        http_get=fake_get,
    )

    result = client.data(
        EiaDataRequest(
            route="electricity/rto/region-data",
            frequency="hourly",
            data_columns=("value",),
            facets=(
                ("respondent", ("CISO",)),
                ("type", ("D",)),
            ),
        )
    )

    assert result.total == 2
    assert len(result.rows) == 2
    assert result.rows[0]["value"] == "42000"
    assert result.complete_page is True


def test_error_payload_is_rejected():
    client = EiaV2Client(
        api_key="test-key",
        http_get=lambda url, headers, timeout: response(
            url,
            {
                "error": {
                    "message": "Invalid route"
                }
            },
        ),
    )

    with pytest.raises(
        SourceResponseError,
        match="Invalid route",
    ):
        client.metadata("bad-route")


def test_external_redirect_is_rejected():
    client = EiaV2Client(
        api_key="test-key",
        http_get=lambda url, headers, timeout: response(
            url,
            METADATA_PAYLOAD,
            final_url="https://untrusted.example/data",
        ),
    )

    with pytest.raises(
        SourceUnauthorizedError,
        match="redirected outside",
    ):
        client.metadata(
            "electricity/rto/region-data"
        )


def test_health_reports_configuration():
    assert EiaV2Client(
        api_key="test-key"
    ).configured is True

    assert EiaV2Client(
        api_key=""
    ).configured is False
