from market_intelligence.connectors.catalog import (
    ProviderAccess,
    matching_providers,
    provider_by_domain,
    provider_by_id,
)
from market_intelligence.routing.capability_router import (
    route_capabilities,
)
from market_intelligence.routing.energy_parser import (
    classify_energy_question,
)


def providers_for(question: str):
    classification = classify_energy_question(question)
    plan = route_capabilities(classification)

    return matching_providers(
        classification,
        plan,
    )


def test_np15_routes_to_caiso_oasis_first():
    providers = providers_for(
        "What prices did NP-15 settle for yesterday?"
    )

    assert providers
    assert providers[0].provider_id == "caiso_oasis"
    assert providers[0].is_primary is True


def test_diablo_routes_to_nrc():
    providers = providers_for(
        "Is Diablo Canyon running at full capacity?"
    )

    assert any(
        provider.provider_id == "nrc_reactor_status"
        for provider in providers
    )


def test_henry_hub_routes_to_eia():
    providers = providers_for(
        "Why did Henry Hub natural gas prices rise?"
    )

    assert any(
        provider.provider_id == "eia_api"
        for provider in providers
    )


def test_ercot_question_routes_to_ercot():
    providers = providers_for(
        "What is ERCOT reserve margin today?"
    )

    assert providers
    assert providers[0].provider_id == "ercot"


def test_ferc_question_routes_to_elibrary():
    providers = providers_for(
        "What new FERC orders affect transmission planning?"
    )

    assert any(
        provider.provider_id == "ferc_elibrary"
        for provider in providers
    )


def test_domain_matching_handles_subdomains_and_urls():
    provider = provider_by_domain(
        "https://elibrary.ferc.gov/eLibrary/"
    )

    assert provider is not None
    assert provider.provider_id == "ferc_elibrary"


def test_licensed_provider_is_excluded_by_default():
    classification = classify_energy_question(
        "What is the latest global energy news?"
    )
    plan = route_capabilities(classification)

    providers = matching_providers(
        classification,
        plan,
    )

    assert all(
        provider.access
        != ProviderAccess.OPTIONAL_LICENSED
        for provider in providers
    )


def test_provider_lookup_by_id():
    provider = provider_by_id("eia_api")

    assert provider is not None
    assert provider.name == (
        "U.S. Energy Information Administration"
    )
