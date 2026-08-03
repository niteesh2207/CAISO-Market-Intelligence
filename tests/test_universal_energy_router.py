import pytest

from market_intelligence.routing.universal_energy_router import (
    EnergyDomain,
    FreshnessNeed,
    ResearchMode,
    route_energy_question,
)


def test_caiso_price_routes_to_electricity_market_data():
    route = route_energy_question(
        "What were NP-15 day-ahead prices yesterday?"
    )

    assert route.domain == (
        EnergyDomain.ELECTRICITY_MARKETS
    )
    assert route.research_mode == (
        ResearchMode.STRUCTURED_DATA
    )
    assert route.freshness == FreshnessNeed.CURRENT
    assert route.geography == "california"
    assert route.providers[0].provider_id == (
        "iso_rto_structured_data"
    )


def test_diablo_canyon_routes_to_nrc():
    route = route_energy_question(
        "Is Diablo Canyon running at full capacity today?"
    )

    assert route.domain == EnergyDomain.NUCLEAR
    assert route.freshness == FreshnessNeed.LIVE
    assert route.providers[0].provider_id == (
        "nrc_reactor_status"
    )
    assert "diablo canyon" in route.matched_entities


def test_henry_hub_routes_to_natural_gas():
    route = route_energy_question(
        "Why did Henry Hub natural gas prices rise?"
    )

    assert route.domain == EnergyDomain.NATURAL_GAS
    assert route.research_mode == (
        ResearchMode.HYBRID_RESEARCH
    )
    assert route.providers[0].provider_id == "eia_api"
    assert route.requires_cross_source_validation is True


def test_brent_routes_to_petroleum():
    route = route_energy_question(
        "What is happening with Brent crude prices?"
    )

    assert route.domain == EnergyDomain.PETROLEUM
    assert route.providers[0].provider_id == "eia_api"


def test_battery_routes_to_storage():
    route = route_energy_question(
        "How much battery capacity is operating in CAISO?"
    )

    assert route.domain == EnergyDomain.ENERGY_STORAGE
    assert route.geography == "california"


def test_solar_curtailment_routes_to_renewables():
    route = route_energy_question(
        "Why was solar curtailment high in California?"
    )

    assert route.domain == EnergyDomain.RENEWABLES
    assert route.research_mode == (
        ResearchMode.HYBRID_RESEARCH
    )


def test_weather_question_routes_to_noaa():
    route = route_energy_question(
        "Will tomorrow's Texas heat affect ERCOT demand?"
    )

    assert route.domain == EnergyDomain.WEATHER
    assert route.geography == "texas"
    assert route.providers[0].provider_id == "noaa_nws"


def test_ferc_order_routes_to_regulatory_documents():
    route = route_energy_question(
        "What new FERC orders affect "
        "transmission planning?"
    )

    assert route.domain == (
        EnergyDomain.TRANSMISSION_REGULATION
    )
    assert route.research_mode == (
        ResearchMode.OFFICIAL_DOCUMENT
    )
    assert route.providers[0].provider_id == (
        "ferc_elibrary"
    )
    assert route.requires_cross_source_validation is True


def test_ercot_reserve_margin_routes_to_reliability():
    route = route_energy_question(
        "What is ERCOT reserve margin today?"
    )

    assert route.domain == EnergyDomain.GRID_RELIABILITY
    assert route.geography == "texas"
    assert route.freshness == FreshnessNeed.LIVE


def test_company_project_routes_to_company_sources():
    route = route_energy_question(
        "What is the latest construction status "
        "of the company's LNG project?"
    )

    assert route.domain == EnergyDomain.COMPANY_ASSET
    assert route.providers[0].provider_id == (
        "company_primary_source"
    )


def test_historical_year_is_detected():
    route = route_energy_question(
        "What was U.S. coal production in 2024?"
    )

    assert route.domain == EnergyDomain.COAL
    assert route.freshness == (
        FreshnessNeed.HISTORICAL
    )


def test_non_energy_question_requests_clarification():
    route = route_energy_question(
        "Who won the tennis match?"
    )

    assert route.domain == EnergyDomain.UNKNOWN
    assert route.research_mode == (
        ResearchMode.CLARIFICATION
    )
    assert route.providers == ()
    assert route.clarification is not None


def test_empty_question_is_rejected():
    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        route_energy_question("   ")


def test_why_was_question_uses_hybrid_research():
    route = route_energy_question(
        "Why was wind curtailment high yesterday?"
    )

    assert route.domain == EnergyDomain.RENEWABLES
    assert route.research_mode == (
        ResearchMode.HYBRID_RESEARCH
    )


def test_standalone_heat_overrides_iso_market_reference():
    route = route_energy_question(
        "Will extreme heat affect CAISO demand tomorrow?"
    )

    assert route.domain == EnergyDomain.WEATHER
    assert route.providers[0].provider_id == "noaa_nws"


def test_weather_market_impact_requires_cross_source_context():
    route = route_energy_question(
        "How will Texas heat affect ERCOT demand?"
    )

    assert route.domain == EnergyDomain.WEATHER
    assert route.research_mode == (
        ResearchMode.HYBRID_RESEARCH
    )


def test_regulatory_affect_language_keeps_document_route():
    route = route_energy_question(
        "How will the latest FERC order affect "
        "regional transmission planning?"
    )

    assert route.domain == (
        EnergyDomain.TRANSMISSION_REGULATION
    )
    assert route.research_mode == (
        ResearchMode.OFFICIAL_DOCUMENT
    )
    assert route.providers[0].provider_id == (
        "ferc_elibrary"
    )


def test_company_latest_status_starts_with_primary_documents():
    route = route_energy_question(
        "What is the latest construction status "
        "of the company's LNG project?"
    )

    assert route.domain == EnergyDomain.COMPANY_ASSET
    assert route.research_mode == (
        ResearchMode.OFFICIAL_DOCUMENT
    )
    assert route.providers[0].provider_id == (
        "company_primary_source"
    )

