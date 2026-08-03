from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from html.parser import HTMLParser
import re
from typing import Callable


from market_intelligence.connectors.catalog import (
    ProviderSpec,
)
from market_intelligence.connectors.official_web import (
    OfficialWebConnector,
)
from market_intelligence.retrieval.exceptions import (
    SourceResponseError,
)
from market_intelligence.retrieval.models import (
    RetrievedRecord,
    RetrievalMethod,
)


NRC_STATUS_URL = (
    "https://www.nrc.gov/reading-rm/"
    "doc-collections/event-status/"
    "reactor-status/ps"
)


@dataclass(frozen=True)
class ReactorUnitStatus:
    unit_name: str
    power_percent: int
    region: int | None = None

    @property
    def online(self) -> bool:
        return self.power_percent > 0

    @property
    def full_capacity(self) -> bool:
        return self.power_percent >= 100


@dataclass(frozen=True)
class ReactorStatusReport:
    report_date: date | None
    units: tuple[ReactorUnitStatus, ...]
    source_title: str
    source_url: str
    retrieved_at: datetime
    collection_timezone: str = "America/New_York"

    def find_units(
        self,
        query: str,
    ) -> tuple[ReactorUnitStatus, ...]:
        normalized = _normalize_name(query)

        exact = [
            unit
            for unit in self.units
            if _normalize_name(unit.unit_name)
            == normalized
        ]

        if exact:
            return tuple(exact)

        matches = [
            unit
            for unit in self.units
            if normalized
            in _normalize_name(unit.unit_name)
        ]

        return tuple(matches)


@dataclass(frozen=True)
class ReactorStatusAnswer:
    question: str
    plant_name: str
    units: tuple[ReactorUnitStatus, ...]
    report_date: date | None
    direct_answer: str
    simple_explanation: str
    source_title: str
    source_url: str
    observed_at: datetime | None
    unit: str = "percent of rated power"


class _NrcTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_region: int | None = None
        self.in_heading = False
        self.heading_parts: list[str] = []
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[tuple[int | None, list[str]]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ) -> None:
        normalized = tag.lower()

        if normalized in {"h2", "h3", "h4"}:
            self.in_heading = True
            self.heading_parts = []

        if normalized in {"td", "th"}:
            self.in_cell = True
            self.cell_parts = []

        if normalized == "tr":
            self.current_row = []

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        normalized = tag.lower()

        if (
            normalized in {"h2", "h3", "h4"}
            and self.in_heading
        ):
            heading = " ".join(
                self.heading_parts
            ).strip()

            match = re.search(
                r"Region\s+(\d+)",
                heading,
                flags=re.IGNORECASE,
            )

            if match:
                self.current_region = int(
                    match.group(1)
                )

            self.in_heading = False

        if (
            normalized in {"td", "th"}
            and self.in_cell
        ):
            value = " ".join(
                self.cell_parts
            ).strip()

            self.current_row.append(value)
            self.in_cell = False

        if normalized == "tr":
            if self.current_row:
                self.rows.append(
                    (
                        self.current_region,
                        list(self.current_row),
                    )
                )

            self.current_row = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        cleaned = re.sub(
            r"\s+",
            " ",
            data,
        ).strip()

        if not cleaned:
            return

        if self.in_heading:
            self.heading_parts.append(cleaned)

        if self.in_cell:
            self.cell_parts.append(cleaned)


def _normalize_name(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        value.lower(),
    ).strip()


def _parse_report_date(
    title: str,
) -> date | None:
    match = re.search(
        r"Report\s+for\s+"
        r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
        title,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return datetime.strptime(
            " ".join(match.groups()),
            "%B %d %Y",
        ).date()
    except ValueError:
        return None


def parse_nrc_reactor_status_html(
    html: str,
    *,
    source_title: str,
    source_url: str,
    retrieved_at: datetime | None = None,
) -> ReactorStatusReport:
    parser = _NrcTableParser()
    parser.feed(html)

    units: list[ReactorUnitStatus] = []

    for region, cells in parser.rows:
        if len(cells) < 2:
            continue

        unit_name = cells[0].strip()
        power_text = cells[1].strip()

        if (
            _normalize_name(unit_name)
            in {"unit", "reactor"}
        ):
            continue

        match = re.search(
            r"-?\d+",
            power_text,
        )

        if not match:
            continue

        power_percent = int(
            match.group(0)
        )

        if not 0 <= power_percent <= 110:
            continue

        units.append(
            ReactorUnitStatus(
                unit_name=unit_name,
                power_percent=power_percent,
                region=region,
            )
        )

    if not units:
        raise SourceResponseError(
            "The NRC status page did not contain "
            "any usable reactor-unit rows."
        )

    return ReactorStatusReport(
        report_date=_parse_report_date(
            source_title
        ),
        units=tuple(units),
        source_title=source_title,
        source_url=source_url,
        retrieved_at=(
            retrieved_at
            or datetime.now(timezone.utc)
        ),
    )


def _plant_display_name(
    query: str,
) -> str:
    cleaned = re.sub(
        r"\bunit\s*\d+\b",
        "",
        query,
        flags=re.IGNORECASE,
    )

    return re.sub(
        r"\s+",
        " ",
        cleaned,
    ).strip()


class NrcReactorStatusConnector:
    connector_id = "nrc_reactor_status"

    def __init__(
        self,
        *,
        official_web: OfficialWebConnector | None = None,
    ) -> None:
        self.official_web = (
            official_web
            or OfficialWebConnector()
        )

    def fetch_report(
        self,
        *,
        provider: ProviderSpec,
        url: str = NRC_STATUS_URL,
    ) -> ReactorStatusReport:
        record = self.official_web.fetch(
            provider=provider,
            url=url,
        )

        payload = record.payload

        raw_html = payload.get("raw_html")

        if raw_html:
            return parse_nrc_reactor_status_html(
                raw_html,
                source_title=record.source_title,
                source_url=record.source_url,
                retrieved_at=record.retrieved_at,
            )

        text = payload.get("text", "")

        return parse_nrc_reactor_status_text(
            text,
            source_title=record.source_title,
            source_url=record.source_url,
            retrieved_at=record.retrieved_at,
        )

    def answer_plant_status(
        self,
        *,
        report: ReactorStatusReport,
        plant_query: str,
        question: str,
    ) -> ReactorStatusAnswer:
        matches = report.find_units(
            plant_query
        )

        if not matches:
            raise SourceResponseError(
                f"No NRC reactor-status rows matched "
                f"{plant_query!r}."
            )

        percentages = [
            unit.power_percent
            for unit in matches
        ]

        full = all(
            percentage >= 100
            for percentage in percentages
        )

        plant_name = _plant_display_name(
            plant_query
        )

        unit_summary = ", ".join(
            f"{unit.unit_name}: "
            f"{unit.power_percent}%"
            for unit in matches
        )

        if full:
            direct_answer = (
                f"Yes. {plant_name} was reported at "
                f"full power in the latest NRC status report."
            )
        elif all(
            percentage == 0
            for percentage in percentages
        ):
            direct_answer = (
                f"No. {plant_name} was reported offline "
                f"in the latest NRC status report."
            )
        else:
            direct_answer = (
                f"No. {plant_name} was not operating at "
                f"full power in the latest NRC status report."
            )

        simple_explanation = (
            f"The NRC listed {unit_summary}. "
            "These values represent reported reactor power "
            "as a percentage of rated power."
        )

        observed_at = None

        if report.report_date is not None:
            observed_at = datetime(
                report.report_date.year,
                report.report_date.month,
                report.report_date.day,
                8,
                0,
                tzinfo=timezone.utc,
            )

        return ReactorStatusAnswer(
            question=question,
            plant_name=plant_name,
            units=matches,
            report_date=report.report_date,
            direct_answer=direct_answer,
            simple_explanation=simple_explanation,
            source_title=report.source_title,
            source_url=report.source_url,
            observed_at=observed_at,
        )


def parse_nrc_reactor_status_text(
    text: str,
    *,
    source_title: str,
    source_url: str,
    retrieved_at: datetime | None = None,
) -> ReactorStatusReport:
    units: list[ReactorUnitStatus] = []
    current_region: int | None = None

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]

    for line in lines:
        region_match = re.search(
            r"Region\s+(\d+)",
            line,
            flags=re.IGNORECASE,
        )

        if region_match:
            current_region = int(
                region_match.group(1)
            )
            continue

        # Accept only an explicit table separator. A generic
        # single-space match is unsafe because a line such as
        # "Diablo Canyon 1" would incorrectly interpret the unit
        # number as the reactor power percentage.
        match = re.match(
            r"(.+?)\s*(?:\||\t|\s{2,})\s*(\d{1,3})$",
            line,
        )

        if not match:
            continue

        unit_name = match.group(1).strip()
        power_percent = int(
            match.group(2)
        )

        if (
            _normalize_name(unit_name)
            in {
                "unit",
                "power",
                "unit power",
            }
        ):
            continue

        if not 0 <= power_percent <= 110:
            continue

        units.append(
            ReactorUnitStatus(
                unit_name=unit_name,
                power_percent=power_percent,
                region=current_region,
            )
        )

    if not units:
        raise SourceResponseError(
            "The NRC extracted text did not contain "
            "usable reactor-unit rows."
        )

    return ReactorStatusReport(
        report_date=_parse_report_date(
            source_title
        ),
        units=tuple(units),
        source_title=source_title,
        source_url=source_url,
        retrieved_at=(
            retrieved_at
            or datetime.now(timezone.utc)
        ),
    )


def answer_to_retrieved_record(
    answer: ReactorStatusAnswer,
) -> RetrievedRecord:
    return RetrievedRecord(
        provider_id="nrc_reactor_status",
        method=RetrievalMethod.OFFICIAL_WEB,
        source_title=answer.source_title,
        source_url=answer.source_url,
        observed_at=answer.observed_at,
        published_at=None,
        retrieved_at=datetime.now(timezone.utc),
        payload={
            "direct_answer": answer.direct_answer,
            "simple_explanation": (
                answer.simple_explanation
            ),
            "plant": answer.plant_name,
            "report_date": (
                answer.report_date.isoformat()
                if answer.report_date
                else None
            ),
            "units": [
                {
                    "unit_name": unit.unit_name,
                    "power_percent": (
                        unit.power_percent
                    ),
                    "region": unit.region,
                }
                for unit in answer.units
            ],
            "unit": answer.unit,
            "market": "U.S. NRC reactor status",
            "timezone": "America/New_York",
            "interval": "daily",
        },
        is_primary=True,
        authority_rank=1,
        metadata={
            "complete_coverage": True,
            "has_unit": True,
            "has_market_context": True,
            "has_timezone": True,
        },
    )
