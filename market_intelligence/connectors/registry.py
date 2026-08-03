from __future__ import annotations

from market_intelligence.connectors.base import MarketDataConnector
from market_intelligence.models.query import MarketQuery


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, MarketDataConnector] = {}

    def register(self, connector: MarketDataConnector) -> None:
        connector_id = connector.capabilities.connector_id

        if connector_id in self._connectors:
            raise ValueError(
                f"Connector already registered: {connector_id}"
            )

        self._connectors[connector_id] = connector

    def all(self) -> list[MarketDataConnector]:
        return list(self._connectors.values())

    def matching(self, query: MarketQuery) -> list[MarketDataConnector]:
        connectors = [
            connector
            for connector in self._connectors.values()
            if connector.supports(query)
        ]

        return sorted(
            connectors,
            key=lambda item: item.capabilities.authority_rank,
        )

    def health(self) -> list[dict[str, str]]:
        return [
            connector.health()
            for connector in self._connectors.values()
        ]
