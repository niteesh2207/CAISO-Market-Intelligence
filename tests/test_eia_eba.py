from datetime import datetime, timezone
from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from market_intelligence.connectors.eia_bulk import (
    EiaBulkArchive,
    EiaBulkFile,
)
from market_intelligence.connectors.eia_eba import (
    build_eba_series_id,
    EbaMetric,
    latest_eba_observation,
    normalize_balancing_authority,
    parse_eba_series,
)
from market_intelligence.retrieval.exceptions import (
    SourceResponseError,
)


def eba_zip(
    records,
    *,
    member_name="EBA.txt",
):
    buffer = BytesIO()

    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            member_name,
            "\n".join(
                json.dumps(record)
                for record in records
            )
            + "\n",
        )

    return buffer.getvalue()


def bulk_archive(records):
    file = EiaBulkFile(
        identifier="EBA",
        data_set="EBA",
        title=(
            "U.S. Electric System Operating Data "
            "(2019-present)"
        ),
        last_updated="2026-08-03",
        modified="2026-08-03T15:30:00-04:00",
        category_id="electricity",
        download_url=(
            "https://www.eia.gov/opendata/bulk/EBA.zip"
        ),
        raw={},
    )

    return EiaBulkArchive(
        file=file,
        final_url=file.download_url,
        retrieved_at=datetime(
            2026,
            8,
            3,
            20,
            0,
            tzinfo=timezone.utc,
        ),
        body=eba_zip(records),
        member_names=("EBA.txt",),
    )


DEMAND_RECORD = {
    "series_id": "EBA.CISO-ALL.D.H",
    "name": (
        "California Independent System Operator "
        "Hourly Demand"
    ),
    "units": "megawatthours",
    "unitsshort": "MWh",
    "f": "H",
    "description": "Hourly demand",
    "last_updated": "2026-08-03T15:30:00-04:00",
    "data": [
        ["20260803T19Z", "39200"],
        ["20260803T18Z", "38100"],
        ["20260803T17Z", "null"],
    ],
}


def test_balancing_authority_aliases():
    assert normalize_balancing_authority(
        "CAISO"
    ) == "CISO"

    assert normalize_balancing_authority(
        "ERCOT"
    ) == "ERCO"

    assert normalize_balancing_authority(
        "SPP"
    ) == "SWPP"


def test_series_id_is_built():
    assert build_eba_series_id(
        "CAISO",
        EbaMetric.DEMAND,
    ) == "EBA.CISO-ALL.D.H"

    assert build_eba_series_id(
        "CAISO",
        EbaMetric.NET_GENERATION,
    ) == "EBA.CISO-ALL.NG.H"


def test_demand_series_is_parsed():
    series = parse_eba_series(
        bulk_archive([DEMAND_RECORD]),
        balancing_authority="CAISO",
        metric=EbaMetric.DEMAND,
    )

    assert series.series_id == "EBA.CISO-ALL.D.H"
    assert series.balancing_authority == "CISO"
    assert series.metric == EbaMetric.DEMAND
    assert series.observation_count == 2
    assert series.latest.value == 39200
    assert series.latest.timestamp_utc == datetime(
        2026,
        8,
        3,
        19,
        tzinfo=timezone.utc,
    )


def test_latest_observation_helper():
    series, observation = latest_eba_observation(
        bulk_archive([DEMAND_RECORD]),
        balancing_authority="California ISO",
        metric="D",
    )

    assert series.series_id == "EBA.CISO-ALL.D.H"
    assert observation.value == 39200


def test_invalid_numeric_values_are_skipped():
    record = dict(DEMAND_RECORD)
    record["data"] = [
        ["20260803T19Z", "--"],
        ["20260803T18Z", "38000"],
    ]

    series = parse_eba_series(
        bulk_archive([record]),
        balancing_authority="CAISO",
        metric="D",
    )

    assert series.observation_count == 1
    assert series.latest.value == 38000


def test_missing_series_is_rejected():
    with pytest.raises(
        SourceResponseError,
        match="was not found",
    ):
        parse_eba_series(
            bulk_archive([DEMAND_RECORD]),
            balancing_authority="ERCOT",
            metric="D",
        )


def test_missing_unit_is_rejected():
    record = dict(DEMAND_RECORD)
    record["units"] = ""
    record["unitsshort"] = ""

    with pytest.raises(
        SourceResponseError,
        match="has no unit",
    ):
        parse_eba_series(
            bulk_archive([record]),
            balancing_authority="CAISO",
            metric="D",
        )


def test_category_objects_are_ignored():
    category = {
        "category_id": "123",
        "name": "California ISO",
        "childseries": [
            "EBA.CISO-ALL.D.H",
        ],
    }

    series = parse_eba_series(
        bulk_archive(
            [
                category,
                DEMAND_RECORD,
            ]
        ),
        balancing_authority="CAISO",
        metric="D",
    )

    assert series.latest.value == 39200


def test_invalid_zip_is_rejected():
    archive = bulk_archive([DEMAND_RECORD])

    invalid = EiaBulkArchive(
        file=archive.file,
        final_url=archive.final_url,
        retrieved_at=archive.retrieved_at,
        body=b"not-a-zip",
        member_names=(),
    )

    with pytest.raises(
        SourceResponseError,
        match="valid ZIP",
    ):
        parse_eba_series(
            invalid,
            balancing_authority="CAISO",
            metric="D",
        )
