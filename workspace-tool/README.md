# CAISO Market Intelligence Workspace

Hosted analyst surface for the CAISO Market Intelligence V4 research engine.

## Execution order

1. `MARKET_INTELLIGENCE_API_URL` routes questions to the existing FastAPI `/api/search` endpoint.
2. `OPENAI_API_KEY` enables current source-grounded research through the Responses API and web search.
3. Credential-free evidence mode answers from the two verified model demonstrations and the approved source policy without inventing current values.

## Source standard

- Controlling sources: CAISO OASIS and official CAISO publications, EIA API v2, NRC, FERC, NOAA/NWS, CEC and CPUC.
- Supporting sources may explain context but cannot replace a controlling dataset for exact price, outage, settlement, operating or regulatory claims.
- Licensed Bloomberg, ICE, S&P Global, Wood Mackenzie, Argus and NGI data requires entitlement and an approved server-side delivery method. Scraping authenticated or paywalled content is prohibited.

Every operational answer should preserve source, interval, units, timezone, publication or observation time, retrieval time, freshness, and limitations.

## Validation

```bash
pnpm install
pnpm run build
node --test tests/rendered-html.test.mjs
```

Research and demonstration only. Not authorized for autonomous trading, bidding, or settlement use.
