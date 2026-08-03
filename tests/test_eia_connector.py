from urllib.parse import (
    parse_qs,
    urlparse,
)

import pytest

from market_intelligence.connectors.eia import (
    EiaConfigurationError,
    EiaConnector,
    EiaQuery,
    EiaResponseError,
)


def test_connector_requires_api_key_for_data_queries():
    connector = EiaConnector(
        api_key="",
        http_get=lambda url, headers: {},
    )

    with pytest.raises(
        EiaConfigurationError,
        match="EIA_API_KEY",
    ):
        connector.build_url(
            EiaQuery(
                route="electricity/rto/region-data/data",
            )
        )


def test_url_builder_preserves_facets_and_data_columns():
    connector = EiaConnector(
        api_key="test-key",
        http_get=lambda url, headers: {},
    )

    url = connector.build_url(
        EiaQuery(
            route="electricity/rto/region-data/data",
            frequency="hourly",
            data=(
                "value",
            ),
            facets={
                "respondent": ("CISO",),
                "type": ("D",),
            },
            start="2026-08-01T00",
            end="2026-08-02T00",
            sort_column="period",
            sort_direction="asc",
            length=1000,
        )
    )

    parsed = urlparse(url)
    parameters = parse_qs(parsed.query)

    assert parsed.path.endswith(
        "/electricity/rto/region-data/data/"
    )
    assert parameters["api_key"] == ["test-key"]
    assert parameters["frequency"] == ["hourly"]
    assert parameters["data[]"] == ["value"]
    assert parameters[
        "facets[respondent][]"
    ] == ["CISO"]
    assert parameters[
        "facets[type][]"
    ] == ["D"]
    assert parameters["length"] == ["1000"]


def test_fetch_normalizes_rows_and_metadata():
    def fake_get(url, headers):
        assert headers["Accept"] == "application/json"

        return {
            "response": {
                "frequency": "hourly",
                "description": "Test route",
                "total": "2",
                "data": [
                    {
                        "period": "2026-08-01T00",
                        "value": 100,
                    },
                    {
                        "period": "2026-08-01T01",
                        "value": 110,
                    },
                ],
            }
        }

    connector = EiaConnector(
        api_key="test-key",
        http_get=fake_get,
    )

    result = connector.fetch(
        EiaQuery(
            route="electricity/rto/region-data/data",
            data=("value",),
        )
    )

    assert result.total == 2
    assert result.frequency == "hourly"
    assert len(result.rows) == 2
    assert result.rows[0]["value"] == 100
    assert result.warnings == ()


def test_fetch_marks_partial_page():
    connector = EiaConnector(
        api_key="test-key",
        http_get=lambda url, headers: {
            "response": {
                "total": 10,
                "data": [
                    {"period": "2026-08-01"}
                ],
            }
        },
    )

    result = connector.fetch(
        EiaQuery(
            route="natural-gas/example/data",
            length=1,
        )
    )

    assert len(result.warnings) == 1
    assert "partial page" in result.warnings[0]


def test_invalid_response_contract_is_rejected():
    connector = EiaConnector(
        api_key="test-key",
        http_get=lambda url, headers: {
            "unexpected": True
        },
    )

    with pytest.raises(
        EiaResponseError,
        match="response",
    ):
        connector.fetch(
            EiaQuery(
                route="electricity/example/data",
            )
        )


def test_metadata_requires_api_key():
    connector = EiaConnector(
        api_key="",
        http_get=lambda url, headers: {},
    )

    with pytest.raises(
        EiaConfigurationError,
        match="EIA_API_KEY",
    ):
        connector.metadata()


def test_metadata_returns_routes_when_configured():
    connector = EiaConnector(
        api_key="test-key",
        http_get=lambda url, headers: {
            "response": {
                "routes": [
                    {
                        "id": "electricity",
                        "name": "Electricity",
                    }
                ]
            }
        },
    )

    payload = connector.metadata()

    assert payload["response"]["routes"][0][
        "id"
    ] == "electricity"


def test_health_reports_configuration_state():
    unconfigured = EiaConnector(
        api_key="",
        http_get=lambda url, headers: {},
    )

    configured = EiaConnector(
        api_key="test-key",
        http_get=lambda url, headers: {},
    )

    assert unconfigured.health()["configured"] is False
    assert configured.health()["configured"] is True
