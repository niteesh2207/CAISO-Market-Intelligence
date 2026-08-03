from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from market_intelligence.connectors.caiso_price_query import (
    build_caiso_date_window,
    build_caiso_price_query,
    CaisoLocationResolutionError,
    CaisoMarket,
    CaisoMarketAmbiguityError,
    CaisoPriceReport,
    resolve_caiso_location,
    resolve_caiso_market,
    resolve_market_date,
)


PACIFIC = ZoneInfo("America/Los_Angeles")


def test_np15_alias_resolves_to_official_location():
    location = resolve_caiso_location("NP-15")

    assert location.display_name == "NP-15"
    assert location.canonical_name == (
        "TH_NP15_GEN-APND"
    )
    assert location.location_type == "trading_hub"


def test_location_can_be_found_inside_question():
    location = resolve_caiso_location(
        "What were SP15 prices yesterday?"
    )

    assert location.display_name == "SP-15"


def test_unsupported_location_is_rejected():
    with pytest.raises(
        CaisoLocationResolutionError,
        match="Unsupported",
    ):
        resolve_caiso_location("Unknown Hub")


def test_day_ahead_market_is_resolved():
    market = resolve_caiso_market(
        "What was the NP-15 day-ahead LMP yesterday?"
    )

    assert market == CaisoMarket.DAY_AHEAD


def test_real_time_market_is_resolved():
    market = resolve_caiso_market(
        "What were NP-15 real-time 5-minute prices?"
    )

    assert market == CaisoMarket.REAL_TIME


def test_market_without_explicit_context_is_unspecified():
    market = resolve_caiso_market(
        "What prices did NP-15 settle for yesterday?"
    )

    assert market == CaisoMarket.UNSPECIFIED


def test_conflicting_market_terms_are_rejected():
    with pytest.raises(
        CaisoMarketAmbiguityError,
        match="multiple",
    ):
        resolve_caiso_market(
            "Compare NP-15 day-ahead and real-time prices."
        )


def test_yesterday_uses_pacific_date():
    now = datetime(
        2026,
        8,
        3,
        1,
        30,
        tzinfo=PACIFIC,
    )

    market_date = resolve_market_date(
        "What was yesterday's price?",
        now=now,
    )

    assert market_date == date(2026, 8, 2)


def test_utc_input_is_converted_to_pacific_before_yesterday():
    now_utc = datetime(
        2026,
        8,
        3,
        6,
        30,
        tzinfo=ZoneInfo("UTC"),
    )

    # 06:30 UTC is still 23:30 Pacific on August 2.
    market_date = resolve_market_date(
        "What was yesterday's price?",
        now=now_utc,
    )

    assert market_date == date(2026, 8, 1)


def test_normal_day_has_24_hour_query_window():
    window = build_caiso_date_window(
        date(2026, 8, 2)
    )

    assert window.local_hours == 24.0


def test_spring_dst_day_has_23_hour_query_window():
    window = build_caiso_date_window(
        date(2026, 3, 8)
    )

    assert window.local_hours == 23.0


def test_fall_dst_day_has_25_hour_query_window():
    window = build_caiso_date_window(
        date(2026, 11, 1)
    )

    assert window.local_hours == 25.0


def test_day_ahead_query_contract():
    query = build_caiso_price_query(
        question=(
            "What was the NP-15 day-ahead price "
            "yesterday?"
        ),
        location="NP-15",
        market_date=date(2026, 8, 2),
    )

    assert query.market == CaisoMarket.DAY_AHEAD
    assert query.report == (
        CaisoPriceReport.LOCATIONAL_MARGINAL_PRICE
    )
    assert query.location.canonical_name == (
        "TH_NP15_GEN-APND"
    )
    assert query.endpoint.startswith("https://")
    assert "queryname=PRC_LMP" in query.url
    assert "market_run_id=DAM" in query.url
    assert "node=TH_NP15_GEN-APND" in query.url


def test_unspecified_market_is_blocked():
    with pytest.raises(
        CaisoMarketAmbiguityError,
        match="Specify",
    ):
        build_caiso_price_query(
            question=(
                "What prices did NP-15 settle "
                "for yesterday?"
            ),
            location="NP-15",
            market_date=date(2026, 8, 2),
        )


def test_non_https_endpoint_is_rejected():
    with pytest.raises(
        ValueError,
        match="HTTPS",
    ):
        build_caiso_price_query(
            question=(
                "What was the NP-15 day-ahead price?"
            ),
            location="NP-15",
            market=CaisoMarket.DAY_AHEAD,
            market_date=date(2026, 8, 2),
            endpoint=(
                "http://oasis.caiso.com/"
                "oasisapi/SingleZip"
            ),
        )


def test_full_written_month_date_is_resolved():
    market_date = resolve_market_date(
        "What were NP-15 day-ahead prices "
        "on August 2, 2026?"
    )

    assert market_date == date(2026, 8, 2)


def test_abbreviated_month_date_is_resolved():
    market_date = resolve_market_date(
        "Give me the price for Aug 2 2026."
    )

    assert market_date == date(2026, 8, 2)


def test_day_first_written_date_is_resolved():
    market_date = resolve_market_date(
        "Give me the price for 2 August 2026."
    )

    assert market_date == date(2026, 8, 2)


def test_invalid_written_date_is_rejected():
    with pytest.raises(
        ValueError,
        match="written CAISO market date is invalid",
    ):
        resolve_market_date(
            "Give me the price for February 30, 2026."
        )

