from source_registry import COMMON_AUTHORITIES, INTENT_DOMAINS


LICENSED_DOMAINS = {
    "bloomberg.com",
    "ice.com",
    "spglobal.com",
    "woodmac.com",
    "argusmedia.com",
    "naturalgasintel.com",
}


def test_public_web_search_excludes_licensed_domains():
    configured = set(COMMON_AUTHORITIES)

    for domains in INTENT_DOMAINS.values():
        configured.update(domains)

    assert configured.isdisjoint(LICENSED_DOMAINS)


def test_price_search_includes_controlling_oasis_domains():
    price_domains = set(INTENT_DOMAINS["price"])

    assert "oasis.caiso.com" in price_domains
    assert "oasis-bulk.caiso.com" in price_domains
