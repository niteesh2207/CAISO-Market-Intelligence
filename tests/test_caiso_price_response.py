from datetime import date, timedelta
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from market_intelligence.connectors.caiso_price_query import (
    build_caiso_price_query,
    CaisoMarket,
)
from market_intelligence.connectors.caiso_price_response import (
    expected_interval_count,
    extract_oasis_csv,
    parse_caiso_price_csv,
    parse_oasis_price_archive,
    summarize_caiso_prices,
    summary_to_retrieved_record,
)
from market_intelligence.retrieval.exceptions import (
    SourceResponseError,
)


def query(
    market=CaisoMarket.DAY_AHEAD,
):
    return build_caiso_price_query(
        question="CAISO price test",
        location="NP-15",
        market=market,
        market_date=date(2026, 8, 2),
    )


def csv_text(
    *,
    count=24,
    duplicate=False,
    component="LMP",
    location="TH_NP15_GEN-APND",
    market="DAM",
):
    selected_query = query(
        {
            "DAM": CaisoMarket.DAY_AHEAD,
            "FMM": CaisoMarket.FIFTEEN_MINUTE,
            "RTM": CaisoMarket.REAL_TIME,
        }[market]
    )

    interval_minutes = {
        "DAM": 60,
        "FMM": 15,
        "RTM": 5,
    }[market]

    lines = [
        (
            "INTERVALSTARTTIME_GMT,"
            "INTERVALENDTIME_GMT,"
            "OPR_DT,OPR_HR,OPR_INTERVAL,"
            "NODE_ID_XML,MARKET_RUN_ID,"
            "LMP_TYPE,MW"
        )
    ]

    for index in range(count):
        start = (
            selected_query.date_window.utc_start
            + timedelta(
                minutes=interval_minutes * index
            )
        )
        end = start + timedelta(
            minutes=interval_minutes
        )

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
                    str(index // max(
                        1,
                        60 // interval_minutes,
                    ) + 1),
                    str(
                        index % max(
                            1,
                            60 // interval_minutes,
                        ) + 1
                    ),
                    location,
                    market,
                    component,
                    str(20 + index),
                ]
            )
        )

    if duplicate:
        lines.append(lines[-1])

    return "\n".join(lines) + "\n"


def zipped(
    content,
    *,
    filename="PRC_LMP_20260802.csv",
):
    buffer = BytesIO()

    with ZipFile(
        buffer,
        "w",
        ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            filename,
            content,
        )

    return buffer.getvalue()


def test_zip_csv_is_extracted():
    name, content = extract_oasis_csv(
        zipped(csv_text())
    )

    assert name.endswith(".csv")
    assert "INTERVALSTARTTIME_GMT" in content


def test_invalid_zip_is_rejected():
    with pytest.raises(
        SourceResponseError,
        match="valid ZIP",
    ):
        extract_oasis_csv(b"not-a-zip")


def test_zip_without_csv_is_rejected():
    with pytest.raises(
        SourceResponseError,
        match="did not contain a CSV",
    ):
        extract_oasis_csv(
            zipped(
                "text",
                filename="readme.txt",
            )
        )


def test_multiple_csv_files_are_rejected():
    buffer = BytesIO()

    with ZipFile(buffer, "w") as archive:
        archive.writestr("one.csv", "a,b\n1,2\n")
        archive.writestr("two.csv", "a,b\n1,2\n")

    with pytest.raises(
        SourceResponseError,
        match="multiple CSV",
    ):
        extract_oasis_csv(
            buffer.getvalue()
        )


def test_day_ahead_csv_parses_24_lmp_rows():
    selected_query = query()

    intervals = parse_caiso_price_csv(
        csv_text(),
        query=selected_query,
    )

    assert len(intervals) == 24
    assert intervals[0].price_usd_per_mwh == 20
    assert intervals[-1].price_usd_per_mwh == 43


def test_non_lmp_components_are_excluded():
    with pytest.raises(
        SourceResponseError,
        match="No matching",
    ):
        parse_caiso_price_csv(
            csv_text(component="MCC"),
            query=query(),
        )


def test_wrong_node_is_excluded():
    with pytest.raises(
        SourceResponseError,
        match="No matching",
    ):
        parse_caiso_price_csv(
            csv_text(location="TH_SP15_GEN-APND"),
            query=query(),
        )


def test_duplicate_intervals_are_rejected():
    with pytest.raises(
        SourceResponseError,
        match="duplicate",
    ):
        parse_caiso_price_csv(
            csv_text(duplicate=True),
            query=query(),
        )


def test_expected_counts_by_market():
    assert expected_interval_count(
        query(CaisoMarket.DAY_AHEAD)
    ) == 24

    assert expected_interval_count(
        query(CaisoMarket.FIFTEEN_MINUTE)
    ) == 96

    assert expected_interval_count(
        query(CaisoMarket.REAL_TIME)
    ) == 288


def test_incomplete_coverage_is_rejected():
    selected_query = query()

    intervals = parse_caiso_price_csv(
        csv_text(count=23),
        query=selected_query,
    )

    with pytest.raises(
        SourceResponseError,
        match="expected 24, received 23",
    ):
        summarize_caiso_prices(
            intervals,
            query=selected_query,
        )


def test_complete_archive_produces_summary():
    selected_query = query()

    summary = parse_oasis_price_archive(
        zipped(csv_text()),
        query=selected_query,
    )

    assert summary.complete_coverage is True
    assert summary.actual_interval_count == 24
    assert summary.average_price == 31.5
    assert summary.minimum_price == 20
    assert summary.maximum_price == 43


def test_summary_becomes_primary_evidence():
    selected_query = query()

    summary = parse_oasis_price_archive(
        zipped(csv_text()),
        query=selected_query,
    )

    record = summary_to_retrieved_record(
        summary
    )

    assert record.provider_id == "caiso_oasis"
    assert record.is_primary is True
    assert record.payload["unit"] == "USD/MWh"
    assert record.payload["complete_coverage"] is True
    assert record.metadata["has_timezone"] is True
