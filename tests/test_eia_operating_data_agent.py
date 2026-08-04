from market_intelligence.connectors.eia_eba import (
    EbaMetric,
)
from market_intelligence.service.eia_operating_data_agent import (
    OperatingDataStatus,
    resolve_authority,
    resolve_metric,
)


def test_caiso_authority_is_resolved():
    assert resolve_authority(
        "What is CAISO demand right now?"
    ) == "CAISO"


def test_ercot_authority_is_resolved():
    assert resolve_authority(
        "What is ERCOT demand?"
    ) == "ERCOT"


def test_demand_metric_is_resolved():
    assert resolve_metric(
        "What is CAISO demand right now?"
    ) == EbaMetric.DEMAND


def test_forecast_precedes_generic_demand():
    assert resolve_metric(
        "What is CAISO's demand forecast?"
    ) == EbaMetric.DEMAND_FORECAST


def test_generation_metric_is_resolved():
    assert resolve_metric(
        "What is PJM net generation?"
    ) == EbaMetric.NET_GENERATION


def test_interchange_metric_is_resolved():
    assert resolve_metric(
        "What is MISO total interchange?"
    ) == EbaMetric.TOTAL_INTERCHANGE
