from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
import re


from market_intelligence.connectors.eia_bulk import (
    EiaBulkArchive,
    EiaBulkClient,
)
from market_intelligence.connectors.eia_eba import (
    EbaMetric,
    EbaObservation,
    EbaSeries,
    latest_eba_observation,
)


class OperatingDataStatus(StrEnum):
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    STALE = "stale"


@dataclass(frozen=True)
class OperatingDataAnswer:
    question: str
    status: OperatingDataStatus
    balancing_authority: str | None
    metric: EbaMetric | None
    direct_answer: str
    simple_explanation: str
    source_url: str | None
    observation_timestamp_utc: datetime | None
    value: float | None
    source_unit: str | None
    equivalent_average_mw: float | None
    age_hours: float | None


AUTHORITY_PATTERNS = {
    "CAISO": (
        r"\bcaiso\b",
        r"\bcalifornia iso\b",
    ),
    "ERCOT": (
        r"\bercot\b",
        r"\btexas grid\b",
    ),
    "PJM": (
        r"\bpjm\b",
    ),
    "MISO": (
        r"\bmiso\b",
        r"\bmidcontinent\b",
    ),
    "SPP": (
        r"\bspp\b",
        r"\bsouthwest power pool\b",
    ),
    "NYISO": (
        r"\bnyiso\b",
        r"\bnew york iso\b",
    ),
    "ISO-NE": (
        r"\biso[ -]?ne\b",
        r"\bnew england iso\b",
    ),
}


METRIC_PATTERNS = {
    EbaMetric.DEMAND_FORECAST: (
        r"\bdemand forecast\b",
        r"\bload forecast\b",
        r"\bforecast demand\b",
    ),
    EbaMetric.NET_GENERATION: (
        r"\bnet generation\b",
        r"\bgeneration\b",
    ),
    EbaMetric.TOTAL_INTERCHANGE: (
        r"\btotal interchange\b",
        r"\binterchange\b",
        r"\bnet imports?\b",
        r"\bnet exports?\b",
    ),
    EbaMetric.DEMAND: (
        r"\bdemand\b",
        r"\bload\b",
    ),
}


def resolve_authority(
    question: str,
) -> str | None:
    normalized = question.lower()

    for authority, patterns in AUTHORITY_PATTERNS.items():
        if any(
            re.search(pattern, normalized)
            for pattern in patterns
        ):
            return authority

    return None


def resolve_metric(
    question: str,
) -> EbaMetric | None:
    normalized = question.lower()

    for metric, patterns in METRIC_PATTERNS.items():
        if any(
            re.search(pattern, normalized)
            for pattern in patterns
        ):
            return metric

    return None


def _is_hourly_energy_unit(
    unit: str,
) -> bool:
    normalized = (
        unit.lower()
        .replace(" ", "")
        .replace("-", "")
    )

    return normalized in {
        "mwh",
        "megawatthours",
        "megawatthour",
    }


class EiaOperatingDataAgent:
    def __init__(
        self,
        *,
        cache_path: str | Path = ".cache/eia/EBA.zip",
        maximum_age_hours: float = 72,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.maximum_age_hours = maximum_age_hours

    def _archive(self) -> EiaBulkArchive:
        if not self.cache_path.exists():
            raise FileNotFoundError(
                f"EBA cache not found: {self.cache_path}"
            )

        client = EiaBulkClient()
        manifest = client.manifest()

        matches = tuple(
            file
            for file in manifest.files
            if file.identifier.upper() == "EBA"
        )

        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one EBA file, found "
                f"{len(matches)}."
            )

        return EiaBulkArchive(
            file=matches[0],
            final_url=matches[0].download_url,
            retrieved_at=datetime.now(timezone.utc),
            body=self.cache_path.read_bytes(),
            member_names=("EBA.txt",),
        )

    def answer(
        self,
        question: str,
    ) -> OperatingDataAnswer:
        cleaned = question.strip()

        if not cleaned:
            raise ValueError(
                "Operating-data question cannot be empty."
            )

        authority = resolve_authority(cleaned)
        metric = resolve_metric(cleaned)

        if authority is None or metric is None:
            missing = []

            if authority is None:
                missing.append(
                    "balancing authority"
                )

            if metric is None:
                missing.append(
                    "metric"
                )

            return OperatingDataAnswer(
                question=cleaned,
                status=(
                    OperatingDataStatus
                    .NEEDS_CLARIFICATION
                ),
                balancing_authority=authority,
                metric=metric,
                direct_answer=(
                    "Please specify the "
                    + " and ".join(missing)
                    + "."
                ),
                simple_explanation=(
                    "Supported metrics include demand, "
                    "demand forecast, net generation and "
                    "total interchange."
                ),
                source_url=None,
                observation_timestamp_utc=None,
                value=None,
                source_unit=None,
                equivalent_average_mw=None,
                age_hours=None,
            )

        series, latest = latest_eba_observation(
            self._archive(),
            balancing_authority=authority,
            metric=metric,
        )

        age_hours = (
            datetime.now(timezone.utc)
            - latest.timestamp_utc
        ).total_seconds() / 3600

        equivalent_mw = (
            latest.value
            if _is_hourly_energy_unit(series.units)
            else None
        )

        stale = age_hours > self.maximum_age_hours

        status = (
            OperatingDataStatus.STALE
            if stale
            else OperatingDataStatus.ANSWERED
        )

        metric_label = {
            EbaMetric.DEMAND: "demand",
            EbaMetric.DEMAND_FORECAST: (
                "day-ahead demand forecast"
            ),
            EbaMetric.NET_GENERATION: "net generation",
            EbaMetric.TOTAL_INTERCHANGE: (
                "total interchange"
            ),
        }[metric]

        direct_answer = (
            f"EIA reported {authority} {metric_label} "
            f"of {latest.value:,.0f} {series.units} "
            f"for the hourly interval ending "
            f"{latest.timestamp_utc.isoformat()}."
        )

        if stale:
            direct_answer += (
                " The observation is older than the "
                "configured freshness threshold."
            )

        explanation = (
            "The value comes from EIA Form EIA-930 "
            f"series {series.series_id}. "
            f"The observation was approximately "
            f"{age_hours:.1f} hours old when retrieved."
        )

        return OperatingDataAnswer(
            question=cleaned,
            status=status,
            balancing_authority=authority,
            metric=metric,
            direct_answer=direct_answer,
            simple_explanation=explanation,
            source_url=series.source_url,
            observation_timestamp_utc=(
                latest.timestamp_utc
            ),
            value=latest.value,
            source_unit=series.units,
            equivalent_average_mw=equivalent_mw,
            age_hours=age_hours,
        )
