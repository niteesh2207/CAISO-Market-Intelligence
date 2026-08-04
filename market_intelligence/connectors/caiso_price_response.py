from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO, StringIO
import csv
import math
import re
from statistics import fmean
from typing import Iterable
from zipfile import BadZipFile, ZipFile


from market_intelligence.connectors.caiso_price_query import (
    CaisoMarket,
    CaisoPriceQuery,
)
from market_intelligence.retrieval.exceptions import (
    SourceResponseError,
)
from market_intelligence.retrieval.models import (
    RetrievedRecord,
    RetrievalMethod,
)


MAX_ARCHIVE_BYTES = 25_000_000
MAX_MEMBER_BYTES = 50_000_000
MAX_ARCHIVE_MEMBERS = 20


@dataclass(frozen=True)
class CaisoPriceInterval:
    interval_start_utc: datetime
    interval_end_utc: datetime
    market_run_id: str
    location: str
    component: str
    price_usd_per_mwh: float
    operating_date: str | None = None
    operating_hour: int | None = None
    operating_interval: int | None = None


@dataclass(frozen=True)
class CaisoPriceSummary:
    query: CaisoPriceQuery
    intervals: tuple[CaisoPriceInterval, ...]
    expected_interval_count: int
    actual_interval_count: int
    complete_coverage: bool
    average_price: float
    minimum_price: float
    maximum_price: float
    minimum_interval_start: datetime
    maximum_interval_start: datetime

    @property
    def unit(self) -> str:
        return "USD/MWh"


_COLUMN_ALIASES = {
    "interval_start": (
        "INTERVALSTARTTIME_GMT",
        "INTERVAL_START_GMT",
        "INTERVALSTARTTIME",
        "STARTTIME_GMT",
    ),
    "interval_end": (
        "INTERVALENDTIME_GMT",
        "INTERVAL_END_GMT",
        "INTERVALENDTIME",
        "ENDTIME_GMT",
    ),
    "market": (
        "MARKET_RUN_ID",
        "MARKET",
    ),
    "location": (
        "NODE_ID_XML",
        "NODE_ID",
        "PNODE_RESMRID",
        "NODE",
        "LOCATION",
    ),
    "component": (
        "LMP_TYPE",
        "XML_DATA_ITEM",
        "DATA_ITEM",
        "COMPONENT",
    ),
    "price": (
        "MW",
        "VALUE",
        "LMP",
        "PRICE",
    ),
    "operating_date": (
        "OPR_DT",
        "OPERATING_DATE",
    ),
    "operating_hour": (
        "OPR_HR",
        "OPERATING_HOUR",
    ),
    "operating_interval": (
        "OPR_INTERVAL",
        "OPERATING_INTERVAL",
        "INTERVAL",
    ),
}


def _normalize_column(value: str) -> str:
    return re.sub(
        r"[^A-Z0-9]+",
        "_",
        value.strip().upper(),
    ).strip("_")


def _normalized_row(
    row: dict[str, str],
) -> dict[str, str]:
    return {
        _normalize_column(key): (
            value.strip()
            if isinstance(value, str)
            else value
        )
        for key, value in row.items()
        if key is not None
    }


def _value(
    row: dict[str, str],
    logical_name: str,
    *,
    required: bool = True,
) -> str | None:
    for alias in _COLUMN_ALIASES[logical_name]:
        normalized = _normalize_column(alias)

        if normalized in row:
            value = row[normalized]

            if value not in {"", None}:
                return str(value).strip()

    if required:
        raise SourceResponseError(
            f"CAISO response is missing the "
            f"{logical_name!r} field."
        )

    return None


def _parse_utc_datetime(value: str) -> datetime:
    cleaned = value.strip()

    formats = (
        "%Y-%m-%dT%H:%M:%S-00:00",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    )

    for format_string in formats:
        try:
            parsed = datetime.strptime(
                cleaned,
                format_string,
            )

            return parsed.replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(
            cleaned.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise SourceResponseError(
            f"Invalid CAISO interval timestamp: "
            f"{value!r}."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(timezone.utc)


def _optional_int(
    value: str | None,
) -> int | None:
    if value in {None, ""}:
        return None

    try:
        return int(float(str(value)))
    except ValueError:
        return None


def _parse_price(value: str) -> float:
    try:
        price = float(value)
    except ValueError as exc:
        raise SourceResponseError(
            f"Invalid CAISO price value: {value!r}."
        ) from exc

    if not math.isfinite(price):
        raise SourceResponseError(
            "CAISO price must be finite."
        )

    return price


def _is_lmp_component(
    component: str,
) -> bool:
    normalized = _normalize_column(component)

    accepted = {
        "LMP",
        "LMP_PRC",
        "LMP_PRICE",
        "LMP_CONG_ENE_LOSS",
    }

    if normalized in accepted:
        return True

    return (
        normalized.endswith("_LMP")
        and "MCE" not in normalized
        and "MCC" not in normalized
        and "MCL" not in normalized
    )


def _market_interval_minutes(
    market: CaisoMarket,
) -> int:
    mapping = {
        CaisoMarket.DAY_AHEAD: 60,
        CaisoMarket.FIFTEEN_MINUTE: 15,
        CaisoMarket.REAL_TIME: 5,
    }

    try:
        return mapping[market]
    except KeyError as exc:
        raise SourceResponseError(
            "Cannot validate an unspecified CAISO market."
        ) from exc


def expected_interval_count(
    query: CaisoPriceQuery,
) -> int:
    duration_minutes = int(
        (
            query.date_window.utc_end
            - query.date_window.utc_start
        ).total_seconds()
        / 60
    )

    interval_minutes = _market_interval_minutes(
        query.market
    )

    quotient, remainder = divmod(
        duration_minutes,
        interval_minutes,
    )

    if remainder:
        raise SourceResponseError(
            "CAISO query window does not align with "
            "the selected market interval."
        )

    return quotient


def _decode_csv(data: bytes) -> str:
    encodings = (
        "utf-8-sig",
        "utf-8",
        "windows-1252",
    )

    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise SourceResponseError(
        "CAISO CSV encoding could not be decoded."
    )


def extract_oasis_csv(
    archive_bytes: bytes,
) -> tuple[str, str]:
    if not archive_bytes:
        raise SourceResponseError(
            "CAISO OASIS returned an empty response."
        )

    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise SourceResponseError(
            "CAISO OASIS archive exceeded the "
            "configured size limit."
        )

    try:
        archive = ZipFile(BytesIO(archive_bytes))
    except BadZipFile as exc:
        raise SourceResponseError(
            "CAISO OASIS response was not a valid ZIP archive."
        ) from exc

    members = [
        info
        for info in archive.infolist()
        if not info.is_dir()
    ]

    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise SourceResponseError(
            "CAISO OASIS archive contained too many files."
        )

    unsafe = [
        info.filename
        for info in members
        if (
            info.filename.startswith(("/", "\\"))
            or ".." in info.filename.replace("\\", "/").split("/")
        )
    ]

    if unsafe:
        raise SourceResponseError(
            "CAISO OASIS archive contained an unsafe path."
        )

    csv_members = [
        info
        for info in members
        if info.filename.lower().endswith(".csv")
    ]

    if not csv_members:
        xml_members = [
            info.filename
            for info in members
            if info.filename.lower().endswith(".xml")
        ]

        if xml_members:
            raise SourceResponseError(
                "CAISO returned XML instead of the requested "
                "CSV result format."
            )

        raise SourceResponseError(
            "CAISO OASIS archive did not contain a CSV file."
        )

    if len(csv_members) != 1:
        raise SourceResponseError(
            "CAISO OASIS archive contained multiple CSV files."
        )

    member = csv_members[0]

    if member.file_size > MAX_MEMBER_BYTES:
        raise SourceResponseError(
            "CAISO OASIS CSV exceeded the configured "
            "uncompressed size limit."
        )

    with archive.open(member) as stream:
        content = stream.read(
            MAX_MEMBER_BYTES + 1
        )

    if len(content) > MAX_MEMBER_BYTES:
        raise SourceResponseError(
            "CAISO OASIS CSV exceeded the configured "
            "read limit."
        )

    return member.filename, _decode_csv(content)


def parse_caiso_price_csv(
    csv_text: str,
    *,
    query: CaisoPriceQuery,
) -> tuple[CaisoPriceInterval, ...]:
    reader = csv.DictReader(
        StringIO(csv_text)
    )

    if not reader.fieldnames:
        raise SourceResponseError(
            "CAISO CSV did not contain a header row."
        )

    parsed: list[CaisoPriceInterval] = []

    expected_location = (
        query.location.canonical_name.upper()
    )
    expected_market = query.market.value.upper()

    for raw_row in reader:
        row = _normalized_row(raw_row)

        location = _value(
            row,
            "location",
        )
        market = _value(
            row,
            "market",
        )
        component = _value(
            row,
            "component",
        )

        if location.upper() != expected_location:
            continue

        if market.upper() != expected_market:
            continue

        if not _is_lmp_component(component):
            continue

        interval_start = _parse_utc_datetime(
            _value(row, "interval_start")
        )
        interval_end = _parse_utc_datetime(
            _value(row, "interval_end")
        )

        if not (
            query.date_window.utc_start
            <= interval_start
            < query.date_window.utc_end
        ):
            continue

        if interval_end <= interval_start:
            raise SourceResponseError(
                "CAISO interval end must be after "
                "interval start."
            )

        parsed.append(
            CaisoPriceInterval(
                interval_start_utc=interval_start,
                interval_end_utc=interval_end,
                market_run_id=market,
                location=location,
                component=component,
                price_usd_per_mwh=_parse_price(
                    _value(row, "price")
                ),
                operating_date=_value(
                    row,
                    "operating_date",
                    required=False,
                ),
                operating_hour=_optional_int(
                    _value(
                        row,
                        "operating_hour",
                        required=False,
                    )
                ),
                operating_interval=_optional_int(
                    _value(
                        row,
                        "operating_interval",
                        required=False,
                    )
                ),
            )
        )

    if not parsed:
        raise SourceResponseError(
            "No matching CAISO LMP rows were found for "
            f"{query.location.display_name} and "
            f"{query.market.value}."
        )

    parsed.sort(
        key=lambda item: item.interval_start_utc
    )

    timestamps = [
        item.interval_start_utc
        for item in parsed
    ]

    if len(timestamps) != len(set(timestamps)):
        raise SourceResponseError(
            "CAISO response contained duplicate LMP "
            "interval timestamps."
        )

    return tuple(parsed)


def summarize_caiso_prices(
    intervals: Iterable[CaisoPriceInterval],
    *,
    query: CaisoPriceQuery,
    require_complete_coverage: bool = True,
) -> CaisoPriceSummary:
    normalized = tuple(intervals)

    if not normalized:
        raise SourceResponseError(
            "Cannot summarize an empty CAISO price result."
        )

    expected = expected_interval_count(query)
    actual = len(normalized)
    complete = actual == expected

    if require_complete_coverage and not complete:
        raise SourceResponseError(
            f"Incomplete CAISO interval coverage: "
            f"expected {expected}, received {actual}."
        )

    prices = [
        interval.price_usd_per_mwh
        for interval in normalized
    ]

    minimum_interval = min(
        normalized,
        key=lambda item: item.price_usd_per_mwh,
    )
    maximum_interval = max(
        normalized,
        key=lambda item: item.price_usd_per_mwh,
    )

    return CaisoPriceSummary(
        query=query,
        intervals=normalized,
        expected_interval_count=expected,
        actual_interval_count=actual,
        complete_coverage=complete,
        average_price=fmean(prices),
        minimum_price=minimum_interval.price_usd_per_mwh,
        maximum_price=maximum_interval.price_usd_per_mwh,
        minimum_interval_start=(
            minimum_interval.interval_start_utc
        ),
        maximum_interval_start=(
            maximum_interval.interval_start_utc
        ),
    )


def parse_oasis_price_archive(
    archive_bytes: bytes,
    *,
    query: CaisoPriceQuery,
    require_complete_coverage: bool = True,
) -> CaisoPriceSummary:
    _, csv_text = extract_oasis_csv(
        archive_bytes
    )

    intervals = parse_caiso_price_csv(
        csv_text,
        query=query,
    )

    return summarize_caiso_prices(
        intervals,
        query=query,
        require_complete_coverage=(
            require_complete_coverage
        ),
    )


def summary_to_retrieved_record(
    summary: CaisoPriceSummary,
    *,
    source_url: str | None = None,
    retrieved_at: datetime | None = None,
) -> RetrievedRecord:
    query = summary.query

    direct_answer = (
        f"{query.location.display_name} "
        f"{query.market.value} LMP averaged "
        f"${summary.average_price:.2f}/MWh on "
        f"{query.date_window.market_date.isoformat()}."
    )

    simple_explanation = (
        f"The official CAISO result contained "
        f"{summary.actual_interval_count} validated intervals. "
        f"The minimum was ${summary.minimum_price:.2f}/MWh "
        f"and the maximum was "
        f"${summary.maximum_price:.2f}/MWh."
    )

    return RetrievedRecord(
        provider_id="caiso_oasis",
        method=RetrievalMethod.STRUCTURED_API,
        source_title=(
            "CAISO OASIS Locational Marginal Prices"
        ),
        source_url=source_url or query.url,
        observed_at=query.date_window.utc_end,
        published_at=None,
        retrieved_at=(
            retrieved_at
            or datetime.now(timezone.utc)
        ),
        payload={
            "direct_answer": direct_answer,
            "simple_explanation": simple_explanation,
            "value": summary.average_price,
            "unit": summary.unit,
            "market": (
                f"CAISO {query.market.value} "
                f"{query.location.display_name}"
            ),
            "timezone": (
                query.date_window.timezone_name
            ),
            "interval": {
                CaisoMarket.DAY_AHEAD: "hourly",
                CaisoMarket.FIFTEEN_MINUTE: "15-minute",
                CaisoMarket.REAL_TIME: "5-minute",
            }[query.market],
            "market_date": (
                query.date_window.market_date.isoformat()
            ),
            "expected_interval_count": (
                summary.expected_interval_count
            ),
            "actual_interval_count": (
                summary.actual_interval_count
            ),
            "complete_coverage": (
                summary.complete_coverage
            ),
            "average_price": summary.average_price,
            "minimum_price": summary.minimum_price,
            "maximum_price": summary.maximum_price,
            "intervals": [
                {
                    "interval_start_utc": (
                        interval.interval_start_utc.isoformat()
                    ),
                    "interval_end_utc": (
                        interval.interval_end_utc.isoformat()
                    ),
                    "price_usd_per_mwh": (
                        interval.price_usd_per_mwh
                    ),
                    "operating_hour": (
                        interval.operating_hour
                    ),
                    "operating_interval": (
                        interval.operating_interval
                    ),
                }
                for interval in summary.intervals
            ],
        },
        is_primary=True,
        authority_rank=1,
        metadata={
            "complete_coverage": (
                summary.complete_coverage
            ),
            "has_unit": True,
            "has_market_context": True,
            "has_timezone": True,
            "calculation_verified": True,
        },
    )
