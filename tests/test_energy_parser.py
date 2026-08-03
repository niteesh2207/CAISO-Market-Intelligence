from market_intelligence.models.domain import (
    EnergyCommodity,
    EnergyTopic,
    GeographicScope,
)
from market_intelligence.routing.energy_parser import (
    classify_energy_question,
)


def test_np15_is_electricity_settlement():
    result = classify_energy_question(
        "What prices did NP-15 settle for yesterday?"
    )

    assert result.commodity == EnergyCommodity.ELECTRICITY
    assert result.topic == EnergyTopic.SETTLEMENT
    assert result.geography == GeographicScope.CALIFORNIA
    assert "NP-15" in result.entities


def test_diablo_is_nuclear_asset_status():
    result = classify_energy_question(
        "Is Diablo Canyon running at full capacity?"
    )

    assert result.commodity == EnergyCommodity.NUCLEAR
    assert result.topic == EnergyTopic.ASSET_STATUS
    assert result.geography == GeographicScope.CALIFORNIA


def test_henry_hub_is_natural_gas_price():
    result = classify_energy_question(
        "Why did Henry Hub natural gas prices rise?"
    )

    assert result.commodity == EnergyCommodity.NATURAL_GAS
    assert result.topic == EnergyTopic.PRICE
    assert "Henry Hub" in result.entities


def test_brent_is_crude_oil_price():
    result = classify_energy_question(
        "What is happening with Brent crude prices?"
    )

    assert result.commodity == EnergyCommodity.CRUDE_OIL
    assert result.topic == EnergyTopic.PRICE
    assert "Brent" in result.entities


def test_battery_question_is_storage():
    result = classify_energy_question(
        "How much battery capacity is operating in CAISO?"
    )

    assert result.commodity == EnergyCommodity.STORAGE
    assert result.geography == GeographicScope.CALIFORNIA
