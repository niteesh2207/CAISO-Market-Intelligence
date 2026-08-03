from datetime import date, timedelta
from io import BytesIO
from zipfile import ZipFile

import pytest

from market_intelligence.connectors.caiso_price_executor import (
    CaisoOasisPriceExecutor,
    OasisDownloadResponse,
)
from market_intelligence.connectors.caiso_price_query import (
    build_caiso_price_query,
    CaisoMarket,
)
from market_intelligence.retrieval.exceptions import (
    SourceResponseError,
    SourceUnauthorizedError,
)


def query():
    return build_caiso_price_query(
        question="NP-15 day-ahead prices",
        location="NP-15",
        market=CaisoMarket.DAY_AHEAD,
        market_date=date(2026, 8, 2),
    )


def complete_csv():
    selected_query = query()

    lines = [
        (
            "INTERVALSTARTTIME_GMT,"
            "INTERVALENDTIME_GMT,"
            "OPR_DT,OPR_HR,OPR_INTERVAL,"
            "NODE_ID_XML,MARKET_RUN_ID,"
            "LMP_TYPE,MW"
        )
    ]

    for index in range(24):
        start = (
            selected_query.date_window.utc_start
            + timedelta(hours=index)
        )
        end = start + timedelta(hours=1)

        lines.append(
            ",".join(
                [
                    start.strftime(
                        "%Y-%m-%dT%H:%M:%S-00:00"
                    ),
                    end.strftime(
                        "%Y-%m-%dT%H:%M:%S-00:00"
                    ),
                    "2026-08-02",
                    str(index + 1),
                    "0",
                    "TH_NP15_GEN-APND",
                    "DAM",
                    "LMP",
                    str(30 + index),
                ]
            )
        )

    return "\n".join(lines) + "\n"


def zip_bytes(
    filename="PRC_LMP.csv",
    content=None,
):
    buffer = BytesIO()

    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            filename,
            content or complete_csv(),
        )

    return buffer.getvalue()


def response(
    *,
    requested_url,
    final_url=None,
    status_code=200,
    body=None,
):
    return OasisDownloadResponse(
        requested_url=requested_url,
        final_url=final_url or requested_url,
        status_code=status_code,
        content_type="application/zip",
        body=body or zip_bytes(),
        headers={},
    )


def test_complete_download_executes():
    selected_query = query()

    executor = CaisoOasisPriceExecutor(
        http_get=lambda url, headers, timeout: response(
            requested_url=url
        )
    )

    summary = executor.execute(
        selected_query
    )

    assert summary.actual_interval_count == 24
    assert summary.complete_coverage is True
    assert summary.average_price == 41.5


def test_execution_creates_primary_record():
    selected_query = query()

    executor = CaisoOasisPriceExecutor(
        http_get=lambda url, headers, timeout: response(
            requested_url=url
        )
    )

    record = executor.execute_to_record(
        selected_query
    )

    assert record.provider_id == "caiso_oasis"
    assert record.is_primary is True
    assert record.payload["unit"] == "USD/MWh"
    assert record.payload["actual_interval_count"] == 24


def test_redirect_outside_caiso_is_rejected():
    selected_query = query()

    executor = CaisoOasisPriceExecutor(
        http_get=lambda url, headers, timeout: response(
            requested_url=url,
            final_url="https://untrusted.example/result.zip",
        )
    )

    with pytest.raises(
        SourceUnauthorizedError,
        match="redirected outside",
    ):
        executor.execute(selected_query)


def test_http_403_is_classified():
    selected_query = query()

    executor = CaisoOasisPriceExecutor(
        http_get=lambda url, headers, timeout: response(
            requested_url=url,
            status_code=403,
        )
    )

    with pytest.raises(
        SourceUnauthorizedError,
        match="403",
    ):
        executor.execute(selected_query)


def test_empty_response_is_rejected():
    selected_query = query()

    executor = CaisoOasisPriceExecutor(
        http_get=lambda url, headers, timeout: OasisDownloadResponse(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="application/zip",
            body=b"",
            headers={},
        )
    )

    with pytest.raises(
        SourceResponseError,
        match="empty",
    ):
        executor.execute(selected_query)


def test_zipped_xml_error_is_exposed():
    selected_query = query()

    xml = """
    <OASISReport>
      <ERR_CODE>1001</ERR_CODE>
      <ERR_DESC>Invalid query parameter</ERR_DESC>
    </OASISReport>
    """

    executor = CaisoOasisPriceExecutor(
        http_get=lambda url, headers, timeout: response(
            requested_url=url,
            body=zip_bytes(
                filename="error.xml",
                content=xml,
            ),
        )
    )

    with pytest.raises(
        SourceResponseError,
        match="Invalid query parameter",
    ):
        executor.execute(selected_query)


def test_plain_xml_error_is_exposed():
    selected_query = query()

    xml = b"""
    <OASISReport>
      <MESSAGE>Requested data is unavailable</MESSAGE>
    </OASISReport>
    """

    executor = CaisoOasisPriceExecutor(
        http_get=lambda url, headers, timeout: response(
            requested_url=url,
            body=xml,
        )
    )

    with pytest.raises(
        SourceResponseError,
        match="Requested data is unavailable",
    ):
        executor.execute(selected_query)
