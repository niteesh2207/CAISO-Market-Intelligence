from __future__ import annotations

from enum import StrEnum


class EnergyCommodity(StrEnum):
    ELECTRICITY = "electricity"
    NATURAL_GAS = "natural_gas"
    CRUDE_OIL = "crude_oil"
    REFINED_PRODUCTS = "refined_products"
    COAL = "coal"
    NUCLEAR = "nuclear"
    RENEWABLES = "renewables"
    STORAGE = "storage"
    CARBON = "carbon"
    HYDROGEN = "hydrogen"
    MULTI_ENERGY = "multi_energy"
    UNKNOWN = "unknown"


class EnergyTopic(StrEnum):
    PRICE = "price"
    SETTLEMENT = "settlement"
    GENERATION = "generation"
    ASSET_STATUS = "asset_status"
    OUTAGE = "outage"
    CONGESTION = "congestion"
    TRANSMISSION = "transmission"
    FUNDAMENTALS = "fundamentals"
    SUPPLY = "supply"
    DEMAND = "demand"
    STORAGE = "storage"
    INVENTORY = "inventory"
    IMPORT_EXPORT = "import_export"
    CAPACITY = "capacity"
    RESERVES = "reserves"
    WEATHER = "weather"
    REGULATORY = "regulatory"
    POLICY = "policy"
    COMPANY = "company"
    PROJECT = "project"
    EMISSIONS = "emissions"
    NEWS = "news"
    GENERAL = "general"


class GeographicScope(StrEnum):
    UNITED_STATES = "united_states"
    CANADA = "canada"
    MEXICO = "mexico"
    EUROPE = "europe"
    ASIA = "asia"
    GLOBAL = "global"
    WESTERN_US = "western_us"
    TEXAS = "texas"
    NORTHEAST_US = "northeast_us"
    MIDWEST_US = "midwest_us"
    SOUTHEAST_US = "southeast_us"
    CALIFORNIA = "california"
    UNKNOWN = "unknown"
