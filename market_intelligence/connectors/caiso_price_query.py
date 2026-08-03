from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import StrEnum
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo


PACIFIC_TIMEZONE = "America/Los_Angeles"
OASIS_SINGLE_ZIP_ENDPOINT = (
    "https://oasis.caiso.com/oasisapi/SingleZip"
)


class CaisoMarket(StrEnum):
    DAY_AHEAD = "DAM"
    FIFTEEN_MINUTE = "FMM"
    REAL_TIME = "RTM"
    UNSPECIFIED = "UNSPECIFIED"


class CaisoPriceReport(StrEnum):
    LOCATIONAL_MARGINAL_PRICE = "PRC_LMP"
    FMM_LOCATIONAL_MARGINAL_PRICE = "PRC_FMM_LMP"
    INTERVAL_LOCATIONAL_MARGINAL_PRICE = "PRC_INTVL_LMP"


class CaisoPriceQueryError(ValueError):
    """Base CAISO price-query error."""


class CaisoMarketAmbiguityError(CaisoPriceQueryError):
    """Question does not identify a unique CAISO market."""


class CaisoLocationResolutionError(CaisoPriceQueryError):
    """Requested CAISO location could not be resolved."""


@dataclass(frozen=True)
class CaisoLocation:
    canonical_name: str
    display_name: str
    location_type: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class CaisoDateWindow:
    market_date: date
    timezone_name: str
    local_start: datetime
    local_end: datetime
    utc_start: datetime
    utc_end: datetime

    @property
    def local_hours(self) -> float:
        return (
            self.utc_end - self.utc_start
        ).total_seconds() / 3600.0


@dataclass(frozen=True)
class CaisoPriceQuery:
    question: str
    location: CaisoLocation
    market: CaisoMarket
    report: CaisoPriceReport
    date_window: CaisoDateWindow
    endpoint: str
    parameters: tuple[tuple[str, str], ...]

    @property
    def url(self) -> str:
        return (
            f"{self.endpoint}?"
            f"{urlencode(self.parameters)}"
        )


CAISO_LOCATIONS: tuple[CaisoLocation, ...] = (
    CaisoLocation(
        canonical_name="TH_NP15_GEN-APND",
        display_name="NP-15",
        location_type="trading_hub",
        aliases=(
            "np15",
            "np-15",
            "np 15",
            "north path 15",
            "northern california trading hub",
        ),
    ),
    CaisoLocation(
        canonical_name="TH_SP15_GEN-APND",
        display_name="SP-15",
        location_type="trading_hub",
        aliases=(
            "sp15",
            "sp-15",
            "sp 15",
            "south path 15",
            "southern california trading hub",
        ),
    ),
    CaisoLocation(
        canonical_name="TH_ZP26_GEN-APND",
        display_name="ZP-26",
        location_type="trading_hub",
        aliases=(
            "zp26",
            "zp-26",
            "zp 26",
            "zone path 26",
        ),
    ),
)


def _normalize(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        value.lower(),
    ).strip()


def resolve_caiso_location(
    value: str,
) -> CaisoLocation:
    normalized = _normalize(value)

    if not normalized:
        raise CaisoLocationResolutionError(
            "CAISO location cannot be empty."
        )

    for location in CAISO_LOCATIONS:
        candidates = {
            _normalize(location.canonical_name),
            _normalize(location.display_name),
            *(
                _normalize(alias)
                for alias in location.aliases
            ),
        }

        if normalized in candidates:
            return location

    embedded_matches = []

    for location in CAISO_LOCATIONS:
        candidates = {
            _normalize(location.display_name),
            *(
                _normalize(alias)
                for alias in location.aliases
            ),
        }

        if any(
            candidate
            and candidate in normalized
            for candidate in candidates
        ):
            embedded_matches.append(location)

    if len(embedded_matches) == 1:
        return embedded_matches[0]

    raise CaisoLocationResolutionError(
        f"Unsupported or ambiguous CAISO location: {value!r}."
    )


def resolve_caiso_market(
    question: str,
) -> CaisoMarket:
    normalized = _normalize(question)

    day_ahead_terms = (
        "day ahead",
        "dayahead",
        "dam",
        "da price",
        "da prices",
        "da lmp",
    )
    fifteen_minute_terms = (
        "fifteen minute",
        "15 minute",
        "15 min",
        "fmm",
        "rt15",
    )
    real_time_terms = (
        "real time",
        "realtime",
        "rtm",
        "5 minute",
        "5 min",
        "rt5",
    )

    matched = []

    if any(term in normalized for term in day_ahead_terms):
        matched.append(CaisoMarket.DAY_AHEAD)

    if any(term in normalized for term in fifteen_minute_terms):
        matched.append(CaisoMarket.FIFTEEN_MINUTE)

    if any(term in normalized for term in real_time_terms):
        matched.append(CaisoMarket.REAL_TIME)

    unique = tuple(dict.fromkeys(matched))

    if len(unique) == 1:
        return unique[0]

    if len(unique) > 1:
        raise CaisoMarketAmbiguityError(
            "The question references multiple CAISO markets."
        )

    return CaisoMarket.UNSPECIFIED


def require_explicit_caiso_market(
    question: str,
) -> CaisoMarket:
    market = resolve_caiso_market(question)

    if market == CaisoMarket.UNSPECIFIED:
        raise CaisoMarketAmbiguityError(
            "Specify day-ahead, fifteen-minute, or "
            "real-time CAISO prices."
        )

    return market


def report_for_market(
    market: CaisoMarket,
) -> CaisoPriceReport:
    mapping = {
        CaisoMarket.DAY_AHEAD:
            CaisoPriceReport.LOCATIONAL_MARGINAL_PRICE,
        CaisoMarket.FIFTEEN_MINUTE:
            CaisoPriceReport.FMM_LOCATIONAL_MARGINAL_PRICE,
        CaisoMarket.REAL_TIME:
            CaisoPriceReport.INTERVAL_LOCATIONAL_MARGINAL_PRICE,
    }

    try:
        return mapping[market]
    except KeyError as exc:
        raise CaisoMarketAmbiguityError(
            "A specific CAISO market is required."
        ) from exc


def resolve_market_date(
    question: str,
    *,
    now: datetime | None = None,
    timezone_name: str = PACIFIC_TIMEZONE,
) -> date:
    zone = ZoneInfo(timezone_name)

    if now is None:
        local_now = datetime.now(zone)
    elif now.tzinfo is None:
        local_now = now.replace(tzinfo=zone)
    else:
        local_now = now.astimezone(zone)

    normalized = _normalize(question)

    if "day before yesterday" in normalized:
        return local_now.date() - timedelta(days=2)

    if "yesterday" in normalized:
        return local_now.date() - timedelta(days=1)

    if "today" in normalized:
        return local_now.date()

    iso_match = re.search(
        r"\b(20\d{2})-(\d{2})-(\d{2})\b",
        question,
    )

    if iso_match:
        year, month, day = map(
            int,
            iso_match.groups(),
        )

        return date(year, month, day)

    # Written U.S. month formats:
    # "August 2, 2026", "Aug 2 2026", and
    # "2 August 2026".
    month_first_match = re.search(
        r"\b("
        r"January|February|March|April|May|June|"
        r"July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
        r")\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(20\d{2})\b",
        question,
        flags=re.IGNORECASE,
    )

    if month_first_match:
        month_text, day_text, year_text = (
            month_first_match.groups()
        )

        normalized_month = month_text.title()

        if normalized_month == "Sept":
            normalized_month = "Sep"

        date_format = (
            "%B %d %Y"
            if len(normalized_month) > 3
            else "%b %d %Y"
        )

        try:
            return datetime.strptime(
                f"{normalized_month} "
                f"{day_text} {year_text}",
                date_format,
            ).date()
        except ValueError as exc:
            raise CaisoPriceQueryError(
                "The written CAISO market date is invalid."
            ) from exc

    day_first_match = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+("
        r"January|February|March|April|May|June|"
        r"July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
        r")\s*,?\s*(20\d{2})\b",
        question,
        flags=re.IGNORECASE,
    )

    if day_first_match:
        day_text, month_text, year_text = (
            day_first_match.groups()
        )

        normalized_month = month_text.title()

        if normalized_month == "Sept":
            normalized_month = "Sep"

        date_format = (
            "%d %B %Y"
            if len(normalized_month) > 3
            else "%d %b %Y"
        )

        try:
            return datetime.strptime(
                f"{day_text} "
                f"{normalized_month} {year_text}",
                date_format,
            ).date()
        except ValueError as exc:
            raise CaisoPriceQueryError(
                "The written CAISO market date is invalid."
            ) from exc

    slash_match = re.search(
        r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b",
        question,
    )

    if slash_match:
        month, day, year = map(
            int,
            slash_match.groups(),
        )

        try:
            return date(year, month, day)
        except ValueError as exc:
            raise CaisoPriceQueryError(
                "The numerical CAISO market date is invalid."
            ) from exc

    raise CaisoPriceQueryError(
        "The CAISO market date could not be resolved."
    )


def build_caiso_date_window(
    market_date: date,
    *,
    timezone_name: str = PACIFIC_TIMEZONE,
) -> CaisoDateWindow:
    zone = ZoneInfo(timezone_name)

    local_start = datetime.combine(
        market_date,
        time.min,
        tzinfo=zone,
    )

    next_date = market_date + timedelta(days=1)

    local_end = datetime.combine(
        next_date,
        time.min,
        tzinfo=zone,
    )

    return CaisoDateWindow(
        market_date=market_date,
        timezone_name=timezone_name,
        local_start=local_start,
        local_end=local_end,
        utc_start=local_start.astimezone(timezone.utc),
        utc_end=local_end.astimezone(timezone.utc),
    )


def _oasis_timestamp(value: datetime) -> str:
    utc_value = value.astimezone(timezone.utc)

    return utc_value.strftime(
        "%Y%m%dT%H:%M-0000"
    )


def build_caiso_price_query(
    *,
    question: str,
    location: str,
    market: CaisoMarket | None = None,
    market_date: date | None = None,
    now: datetime | None = None,
    endpoint: str = OASIS_SINGLE_ZIP_ENDPOINT,
) -> CaisoPriceQuery:
    if not endpoint.lower().startswith("https://"):
        raise CaisoPriceQueryError(
            "CAISO OASIS endpoint must use HTTPS."
        )

    resolved_location = resolve_caiso_location(location)

    resolved_market = (
        market
        if market is not None
        else require_explicit_caiso_market(question)
    )

    if resolved_market == CaisoMarket.UNSPECIFIED:
        raise CaisoMarketAmbiguityError(
            "A specific CAISO market is required."
        )

    resolved_date = (
        market_date
        if market_date is not None
        else resolve_market_date(
            question,
            now=now,
        )
    )

    date_window = build_caiso_date_window(
        resolved_date
    )

    report = report_for_market(
        resolved_market
    )

    parameters = [
        ("queryname", report.value),
        (
            "startdatetime",
            _oasis_timestamp(date_window.utc_start),
        ),
        (
            "enddatetime",
            _oasis_timestamp(date_window.utc_end),
        ),
        ("version", "1"),
        ("market_run_id", resolved_market.value),
        ("node", resolved_location.canonical_name),
        ("resultformat", "6"),
    ]

    return CaisoPriceQuery(
        question=question.strip(),
        location=resolved_location,
        market=resolved_market,
        report=report,
        date_window=date_window,
        endpoint=endpoint,
        parameters=tuple(parameters),
    )
