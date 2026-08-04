from market_intelligence.api.adapter import (
    universal_answer_to_response,
)
from market_intelligence.routing.universal_energy_router import (
    EnergyDomain,
)
from market_intelligence.service.universal_orchestrator import (
    UniversalAnswer,
    UniversalAnswerStatus,
    UniversalSource,
)


def test_universal_answer_is_serialized():
    answer = UniversalAnswer(
        question="What is CAISO demand?",
        status=UniversalAnswerStatus.ANSWERED,
        domain=EnergyDomain.ELECTRICITY_MARKETS,
        direct_answer="CAISO demand was 37,944 MW.",
        simple_explanation=(
            "The value came from EIA Form EIA-930."
        ),
        confidence="high",
        sources=(
            UniversalSource(
                title="EIA operating data",
                url=(
                    "https://www.eia.gov/"
                    "opendata/bulk/EBA.zip"
                ),
                provider_id="eia_bulk_eba",
                is_primary=True,
            ),
        ),
        evidence_payload={
            "value": 37944,
            "unit": "MW",
        },
    )

    result = universal_answer_to_response(answer)

    assert result.status == "answered"
    assert result.domain == "electricity_markets"
    assert result.confidence == "high"
    assert result.evidence["value"] == 37944
    assert result.sources[0].provider == (
        "eia_bulk_eba"
    )
    assert result.sources[0].primary is True


def test_held_answer_preserves_limitations():
    answer = UniversalAnswer(
        question="What is the value?",
        status=UniversalAnswerStatus.HELD,
        domain=EnergyDomain.ELECTRICITY_MARKETS,
        direct_answer="The answer was held.",
        simple_explanation=(
            "Mandatory evidence was incomplete."
        ),
        confidence="insufficient",
        limitations=(
            "Missing verified unit.",
        ),
    )

    result = universal_answer_to_response(answer)

    assert result.status == "held"
    assert result.limitations == [
        "Missing verified unit."
    ]
