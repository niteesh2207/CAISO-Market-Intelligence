# Source and Acquisition Policy — verified August 7, 2026

CAISO Market Intelligence uses the highest-quality source that is legally and technically available. "Premium" means an entitled commercial feed or delivery channel; it does not mean scraping a paywall, login page, search-result snippet, or licensed publication.

## Tier 1 — controlling structured sources

- [CAISO OASIS](https://oasis.caiso.com/) API and bulk downloads for market prices, LMP components, congestion, and other published market data
- official CAISO market reports, notices, outage publications, and operating-system data
- [EIA API v2](https://www.eia.gov/opendata/documentation.php) and EIA bulk downloads
- [NRC Power Reactor Status Reports](https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/index)
- [FERC Data API](https://data.ferc.gov/developer/gettingstarted/understanding-our-apis/) and official FERC filings
- NOAA/NWS APIs and official observations or forecasts
- CEC, CPUC, BPA, and relevant balancing-authority or utility publications

For exact settlement, price, LMP-component, binding-constraint, outage, or regulatory claims, a controlling structured source is required whenever one exists.

## Tier 2 — authoritative public context

- official agency, balancing-authority, utility, issuer, or exchange publications
- Reuters reporting for corroborating context
- SEC filings and official company investor-relations releases

Tier 2 sources may explain context, but they do not replace a controlling source for exact operational or settlement facts.

## Tier 3 — entitled premium sources

Potential enterprise integrations include Bloomberg, ICE, S&P Global, Wood Mackenzie, Argus, and Natural Gas Intelligence. They are disabled by default and require all of the following:

1. a valid organizational license and entitlement for the requested dataset;
2. an authenticated server-side connector;
3. an approved API, bulk download, SFTP, cloud-delivery, or controlled file-import method;
4. provider-specific retention, redistribution, attribution, and audit controls;
5. secrets stored outside source control;
6. provenance metadata that identifies the provider, dataset, observation time, retrieval time, and entitlement-controlled delivery method.

The public repository does not contain premium credentials or licensed records.

## Prohibited acquisition methods

- scraping authenticated pages, paywalls, terminals, or subscriber-only publications;
- bypassing access controls, robots rules, rate limits, or provider terms;
- treating public search snippets as licensed-feed data;
- copying or redistributing licensed raw data without contractual permission;
- silently substituting secondary reporting for a controlling official dataset.

## Freshness and quality gates

Every material record should carry source URL or dataset identifier, market interval, units, timezone, publication or observation timestamp, and retrieval timestamp. Stale, incomplete, unit-ambiguous, or provenance-free data must be held or clearly qualified rather than presented as current fact.

The source-policy code defaults to public official sources. Licensed providers are excluded unless the caller explicitly supplies an entitled provider identifier, and the generic official-web connector rejects licensed providers even when their domains are known.
