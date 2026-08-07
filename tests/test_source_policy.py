from market_intelligence.models.query import (
    Market,
    QueryIntent,
)
from market_intelligence.research.source_policy import (
    AccessType,
    matching_sources,
    source_by_domain,
)


def test_caiso_price_sources_prioritize_oasis():
    sources = matching_sources(
        market=Market.CAISO,
        intent=QueryIntent.PRICE,
    )

    assert sources
    assert sources[0].source_id == "caiso_oasis"
    assert sources[0].is_primary is True


def test_nrc_domain_is_primary_authority():
    source = source_by_domain(
        "www.nrc.gov"
    )

    assert source is not None
    assert source.source_id == "nrc"
    assert source.is_primary is True


def test_unknown_domain_has_no_authority_match():
    assert source_by_domain(
        "unverified-example.invalid"
    ) is None


def test_licensed_sources_require_explicit_opt_in():
    public_sources = matching_sources(
        market=Market.GENERAL,
        intent=QueryIntent.NEWS,
    )
    entitled_sources = matching_sources(
        market=Market.GENERAL,
        intent=QueryIntent.NEWS,
        include_licensed=True,
    )

    assert all(
        source.access_type != AccessType.LICENSED_OPTIONAL
        for source in public_sources
    )
    assert any(
        source.access_type == AccessType.LICENSED_OPTIONAL
        for source in entitled_sources
    )
