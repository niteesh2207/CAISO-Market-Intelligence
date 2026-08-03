from market_intelligence.models.domain import (
    EnergyCommodity,
    EnergyTopic,
    GeographicScope,
)
from market_intelligence.routing.capability_router import (
    RetrievalCapability,
    route_capabilities,
)
from market_intelligence.routing.energy_parser import (
    EnergyClassification,
)


def classification(
    topic: EnergyTopic,
) -> EnergyClassification:
    return EnergyClassification(
        commodity=EnergyCommodity.ELECTRICITY,
        topic=topic,
        geography=GeographicScope.UNITED_STATES,
        entities=(),
        keywords=(),
    )


def test_price_requires_structured_and_web_sources():
    plan = route_capabilities(
        classification(EnergyTopic.PRICE)
    )

    assert (
        RetrievalCapability.STRUCTURED_MARKET_DATA
        in plan.capabilities
    )
    assert (
        RetrievalCapability.GENERAL_WEB_RESEARCH
        in plan.capabilities
    )
    assert plan.requires_exact_numeric_source is True
    assert plan.requires_cross_check is True
    assert plan.minimum_sources == 2


def test_asset_status_uses_status_and_web_research():
    plan = route_capabilities(
        classification(EnergyTopic.ASSET_STATUS)
    )

    assert (
        RetrievalCapability.ASSET_STATUS
        in plan.capabilities
    )
    assert plan.requires_current_source is True


def test_regulatory_question_uses_documents():
    plan = route_capabilities(
        classification(EnergyTopic.REGULATORY)
    )

    assert (
        RetrievalCapability.REGULATORY_DOCUMENTS
        in plan.capabilities
    )


def test_general_question_still_uses_web_research():
    plan = route_capabilities(
        classification(EnergyTopic.GENERAL)
    )

    assert plan.capabilities == (
        RetrievalCapability.GENERAL_WEB_RESEARCH,
    )
    assert plan.minimum_sources == 1
