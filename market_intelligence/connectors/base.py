from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from market_intelligence.models.evidence import EvidenceItem
from market_intelligence.models.query import MarketQuery


@dataclass(frozen=True)
class ConnectorCapabilities:
    connector_id: str
    markets: tuple[str, ...]
    intents: tuple[str, ...]
    is_structured: bool
    authority_rank: int


class MarketDataConnector(ABC):
    @property
    @abstractmethod
    def capabilities(self) -> ConnectorCapabilities:
        raise NotImplementedError

    @abstractmethod
    def supports(self, query: MarketQuery) -> bool:
        raise NotImplementedError

    @abstractmethod
    def fetch(self, query: MarketQuery) -> list[EvidenceItem]:
        raise NotImplementedError

    def health(self) -> dict[str, str]:
        return {
            "connector": self.capabilities.connector_id,
            "status": "available",
        }
