from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EnergySearchRequest(BaseModel):
    question: str = Field(
        min_length=2,
        max_length=3000,
    )

    allow_web_fallback: bool = True


class EnergySourceResponse(BaseModel):
    provider: str
    title: str
    url: str
    primary: bool
    role: str
    published_at: str | None = None
    retrieved_at: str | None = None
    freshness: str | None = None


class EnergySearchResponse(BaseModel):
    status: Literal[
        "answered",
        "needs_clarification",
        "research_required",
        "held",
    ]

    domain: str
    answer: str
    explanation: str
    confidence: str

    evidence: dict[str, Any] = Field(
        default_factory=dict
    )

    sources: list[EnergySourceResponse] = Field(
        default_factory=list
    )

    limitations: list[str] = Field(
        default_factory=list
    )

    clarification_options: list[str] = Field(
        default_factory=list
    )

    route: dict[str, Any] | None = None

    used_web_fallback: bool = False


class EnergyStatusResponse(BaseModel):
    status: str
    service: str
    version: str
    universal_orchestrator: bool
    eia_cache_available: bool
    openai_configured: bool


class EnergyCapabilityResponse(BaseModel):
    capability: str
    status: str
    controlling_source: str
    examples: list[str]
