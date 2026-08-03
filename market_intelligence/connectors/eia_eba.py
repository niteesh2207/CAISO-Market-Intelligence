from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from io import BytesIO, TextIOWrapper
import json
import math
from typing import Any, Iterable
from zipfile import BadZipFile, ZipFile


from market_intelligence.connectors.eia_bulk import (
    EiaBulkArchive,
)
from market_intelligence.retrieval.exceptions import (
    SourceResponseError,
)


class EbaMetric(StrEnum):
    DEMAND = "D"
    DEMAND_FORECAST = "DF"
    NET_GENERATION = "NG"
    TOTAL_INTERCHANGE = "TI"


METRIC_LABELS = {
    EbaMetric.DEMAND: "demand",
    EbaMetric.DEMAND_FORECAST: "day-ahead demand forecast",
    EbaMetric.NET_GENERATION: "net generation",
    EbaMetric.TOTAL_INTERCHANGE: "total interchange",
}


BALANCING_AUTHORITIES = {
    "CAISO": "CISO",
    "CISO": "CISO",
    "CALIFORNIA ISO": "CISO",
    "ERCOT": "ERCO",
    "ERCO": "ERCO",
    "PJM": "PJM",
    "MISO": "MISO",
    "SPP": "SWPP",
    "SWPP": "SWPP",
    "NYISO": "NYIS",
    "NYIS": "NYIS",
    "ISO-NE": "ISNE",
    "ISO NE": "ISNE",
    "ISONE": "ISNE",
    "ISNE": "ISNE",
}


@dataclass(frozen=True)
class EbaObservation:
    period: str
    timestamp_utc: datetime
    value: float


@dataclass(frozen=True)
class EbaSeries:
    series_id: str
    balancing_authority: str
    metric: EbaMetric
    name: str
    description: str | None
    units: str
    frequency: str
    last_updated: str | None
    observations: tuple[EbaObservation, ...]
    source_url: str
    retrieved_at: datetime

    @property
    def latest(self) -> EbaObservation:
        if not self.observations:
            raise SourceResponseError(
                "The EBA series contains no valid observations."
            )

        return max(
            self.observations,
            key=lambda item: item.timestamp_utc,
        )

    @property
    def observation_count(self) -> int:
        return len(self.observations)


def normalize_balancing_authority(
    value: str,
) -> str:
    cleaned = " ".join(
        value.upper().replace("_", " ").split()
    )

    try:
        return BALANCING_AUTHORITIES[cleaned]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported balancing authority {value!r}."
        ) from exc


def build_eba_series_id(
    balancing_authority: str,
    metric: EbaMetric | str,
) -> str:
    authority = normalize_balancing_authority(
        balancing_authority
    )

    resolved_metric = (
        metric
        if isinstance(metric, EbaMetric)
        else EbaMetric(str(metric).upper())
    )

    return (
        f"EBA.{authority}-ALL."
        f"{resolved_metric.value}.H"
    )


def _parse_period(
    value: Any,
) -> datetime:
    period = str(value).strip()

    formats = (
        "%Y%m%dT%HZ",
        "%Y%m%dT%H",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H%z",
        "%Y-%m-%dT%H",
    )

    for format_string in formats:
        try:
            parsed = datetime.strptime(
                period,
                format_string,
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )
            else:
                parsed = parsed.astimezone(
                    timezone.utc
                )

            return parsed

        except ValueError:
            continue

    normalized = period.replace(
        "Z",
        "+00:00",
    )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError as exc:
        raise SourceResponseError(
            f"Unsupported EBA period {period!r}."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(timezone.utc)


def _parse_numeric(
    value: Any,
) -> float | None:
    if value is None:
        return None

    cleaned = str(value).strip()

    if not cleaned or cleaned.lower() in {
        "null",
        "none",
        "na",
        "n/a",
        "--",
    }:
        return None

    try:
        numeric = float(cleaned)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numeric):
        return None

    return numeric


def _series_objects(
    archive_body: bytes,
) -> Iterable[dict[str, Any]]:
    try:
        with ZipFile(
            BytesIO(archive_body)
        ) as archive:
            members = [
                info
                for info in archive.infolist()
                if not info.is_dir()
                and info.filename.lower().endswith(
                    (".txt", ".json", ".jsonl")
                )
            ]

            if not members:
                raise SourceResponseError(
                    "The EBA ZIP contains no JSON-lines "
                    "text member."
                )

            for member in members:
                with archive.open(member, "r") as raw:
                    with TextIOWrapper(
                        raw,
                        encoding="utf-8-sig",
                        errors="strict",
                        newline=None,
                    ) as stream:
                        for line_number, line in enumerate(
                            stream,
                            start=1,
                        ):
                            stripped = line.strip()

                            if not stripped:
                                continue

                            try:
                                item = json.loads(stripped)
                            except json.JSONDecodeError as exc:
                                raise SourceResponseError(
                                    "Invalid JSON in EBA archive "
                                    f"member {member.filename!r}, "
                                    f"line {line_number}."
                                ) from exc

                            if (
                                isinstance(item, dict)
                                and item.get("series_id")
                            ):
                                yield item

    except BadZipFile as exc:
        raise SourceResponseError(
            "The EBA archive is not a valid ZIP file."
        ) from exc


def _observations_from_record(
    record: dict[str, Any],
) -> tuple[EbaObservation, ...]:
    raw_data = record.get("data")

    if not isinstance(raw_data, list):
        raise SourceResponseError(
            "The EBA series is missing its data array."
        )

    observations: list[EbaObservation] = []

    for item in raw_data:
        period: Any
        value: Any

        if (
            isinstance(item, list)
            and len(item) >= 2
        ):
            period, value = item[0], item[1]

        elif isinstance(item, dict):
            period = (
                item.get("period")
                or item.get("timestamp")
                or item.get("date")
            )
            value = item.get("value")

        else:
            continue

        numeric = _parse_numeric(value)

        if period is None or numeric is None:
            continue

        observations.append(
            EbaObservation(
                period=str(period),
                timestamp_utc=_parse_period(period),
                value=numeric,
            )
        )

    if not observations:
        raise SourceResponseError(
            "The EBA series contains no valid numerical "
            "observations."
        )

    deduplicated = {
        item.timestamp_utc: item
        for item in observations
    }

    return tuple(
        sorted(
            deduplicated.values(),
            key=lambda item: item.timestamp_utc,
        )
    )


def parse_eba_series(
    archive: EiaBulkArchive,
    *,
    balancing_authority: str,
    metric: EbaMetric | str,
) -> EbaSeries:
    authority = normalize_balancing_authority(
        balancing_authority
    )

    resolved_metric = (
        metric
        if isinstance(metric, EbaMetric)
        else EbaMetric(str(metric).upper())
    )

    expected_id = build_eba_series_id(
        authority,
        resolved_metric,
    )

    matched: dict[str, Any] | None = None

    for record in _series_objects(
        archive.body
    ):
        if (
            str(record.get("series_id", "")).strip()
            == expected_id
        ):
            matched = record
            break

    if matched is None:
        raise SourceResponseError(
            f"EBA series {expected_id!r} was not found "
            "in the official archive."
        )

    units = str(
        matched.get("units")
        or matched.get("unitsshort")
        or ""
    ).strip()

    if not units:
        raise SourceResponseError(
            f"EBA series {expected_id!r} has no unit."
        )

    frequency = str(
        matched.get("f")
        or ""
    ).strip()

    if frequency and frequency.upper() != "H":
        raise SourceResponseError(
            f"EBA series {expected_id!r} is not hourly."
        )

    return EbaSeries(
        series_id=expected_id,
        balancing_authority=authority,
        metric=resolved_metric,
        name=str(
            matched.get("name")
            or expected_id
        ).strip(),
        description=(
            str(matched["description"]).strip()
            if matched.get("description") is not None
            else None
        ),
        units=units,
        frequency=frequency or "H",
        last_updated=(
            str(matched["last_updated"]).strip()
            if matched.get("last_updated") is not None
            else None
        ),
        observations=_observations_from_record(
            matched
        ),
        source_url=archive.final_url,
        retrieved_at=archive.retrieved_at,
    )


def latest_eba_observation(
    archive: EiaBulkArchive,
    *,
    balancing_authority: str,
    metric: EbaMetric | str,
) -> tuple[EbaSeries, EbaObservation]:
    series = parse_eba_series(
        archive,
        balancing_authority=balancing_authority,
        metric=metric,
    )

    return series, series.latest
