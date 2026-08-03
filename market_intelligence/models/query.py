from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Market(StrEnum):
    CAISO = "CAISO"
    ERCOT = "ERCOT"
    PJM = "PJM"
    MISO = "MISO"
    SPP = "SPP"
    NYISO = "NYISO"
    ISO_NE = "ISO-NE"
    WEST = "WEST"
    GENERAL = "GENERAL"


class QueryIntent(StrEnum):
    PRICE = "price"
    GENERATION = "generation"
    OUTAGE = "outage"
    CONGESTION = "congestion"
    FUNDAMENTALS = "fundamentals"
    GAS = "gas"
    WEATHER = "weather"
    REGULATORY = "regulatory"
    NEWS = "news"
    GENERAL = "general"


class MarketQuery(BaseModel):
    raw_question: str = Field(min_length=2, max_length=3000)
    market: Market = Market.GENERAL
    intent: QueryIntent = QueryIntent.GENERAL
    timezone: str = "America/Los_Angeles"
    requested_date: date | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    nodes: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
