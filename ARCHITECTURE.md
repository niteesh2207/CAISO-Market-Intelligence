# Architecture

```text
User
  |
  v
Question Router
  |
  +--> Structured market-data connectors
  |      - CAISO OASIS
  |      - BPA
  |      - NRC / weather
  |
  +--> Live web research
  |      - CAISO / regulators / utilities
  |      - reputable secondary market sources
  |
  +--> Licensed connectors (only when authorized)
         - ICE / S&P / Bloomberg / etc.
  |
  v
Freshness + Source Authority + Conflict Checks
  |
  v
LLM Synthesis
  |
  v
Concise Answer + Clickable Evidence
```

The server interprets relative dates in `America/Los_Angeles`.
