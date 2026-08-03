import pytest

from market_intelligence.connectors.eia_eba import (
    build_eba_series_id,
    EbaMetric,
    normalize_balancing_authority,
)
from market_intelligence.service.eia_operating_data_agent import (
    resolve_authority,
    resolve_metric,
)


@pytest.mark.parametrize(
    (
        "question",
        "expected_authority",
        "expected_metric",
    ),
    [
        (
            "What is CAISO demand right now?",
            "CAISO",
            EbaMetric.DEMAND,
        ),
        (
            "What is ERCOT demand right now?",
            "ERCOT",
            EbaMetric.DEMAND,
        ),
        (
            "What is PJM net generation?",
            "PJM",
            EbaMetric.NET_GENERATION,
        ),
        (
            "What is MISO total interchange?",
            "MISO",
            EbaMetric.TOTAL_INTERCHANGE,
        ),
        (
            "What is SPP demand forecast?",
            "SPP",
            EbaMetric.DEMAND_FORECAST,
        ),
        (
            "What is NYISO demand?",
            "NYISO",
            EbaMetric.DEMAND,
        ),
        (
            "What is ISO-NE demand?",
            "ISO-NE",
            EbaMetric.DEMAND,
        ),
    ],
)
def test_multi_iso_question_resolution(
    question,
    expected_authority,
    expected_metric,
):
    assert resolve_authority(question) == (
        expected_authority
    )

    assert resolve_metric(question) == (
        expected_metric
    )


@pytest.mark.parametrize(
    (
        "authority",
        "metric",
        "expected_series",
    ),
    [
        (
            "CAISO",
            EbaMetric.DEMAND,
            "EBA.CISO-ALL.D.H",
        ),
        (
            "ERCOT",
            EbaMetric.DEMAND,
            "EBA.ERCO-ALL.D.H",
        ),
        (
            "PJM",
            EbaMetric.NET_GENERATION,
            "EBA.PJM-ALL.NG.H",
        ),
        (
            "MISO",
            EbaMetric.TOTAL_INTERCHANGE,
            "EBA.MISO-ALL.TI.H",
        ),
        (
            "SPP",
            EbaMetric.DEMAND_FORECAST,
            "EBA.SWPP-ALL.DF.H",
        ),
        (
            "NYISO",
            EbaMetric.DEMAND,
            "EBA.NYIS-ALL.D.H",
        ),
        (
            "ISO-NE",
            EbaMetric.DEMAND,
            "EBA.ISNE-ALL.D.H",
        ),
    ],
)
def test_multi_iso_series_identifiers(
    authority,
    metric,
    expected_series,
):
    assert build_eba_series_id(
        authority,
        metric,
    ) == expected_series


@pytest.mark.parametrize(
    (
        "input_name",
        "expected_code",
    ),
    [
        ("CAISO", "CISO"),
        ("ERCOT", "ERCO"),
        ("PJM", "PJM"),
        ("MISO", "MISO"),
        ("SPP", "SWPP"),
        ("NYISO", "NYIS"),
        ("ISO-NE", "ISNE"),
    ],
)
def test_balancing_authority_code_mapping(
    input_name,
    expected_code,
):
    assert normalize_balancing_authority(
        input_name
    ) == expected_code
