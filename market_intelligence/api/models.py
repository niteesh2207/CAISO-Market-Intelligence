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
    source_id: int | None = None
    source_tier: str | None = None
    retrieved_at: str | None = None


class EnergyClaimResponse(BaseModel):
    text: str
    source_ids: list[int] = Field(
        default_factory=list
    )
    claim_type: str = "fact"


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

    claims: list[EnergyClaimResponse] = Field(
        default_factory=list
    )

    limitations: list[str] = Field(
        default_factory=list
    )

    as_of: str | None = None

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
