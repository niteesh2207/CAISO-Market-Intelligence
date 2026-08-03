from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from market_intelligence.answers.models import (
    AnswerPacket,
)
from market_intelligence.connectors.catalog import (
    ProviderSpec,
)
from market_intelligence.quality.models import (
    ClaimType,
    QualityAssessment,
)
from market_intelligence.retrieval.models import (
    RetrievalOutcome,
)
from market_intelligence.routing.capability_router import (
    CapabilityPlan,
)
from market_intelligence.routing.energy_parser import (
    EnergyClassification,
)


class ResearchStatus(StrEnum):
    ANSWERED = "answered"
    ANSWERED_WITH_WARNING = "answered_with_warning"
    HELD = "held"
    FAILED = "failed"


@dataclass(frozen=True)
class ResearchRequest:
    question: str
    claim_type: ClaimType
    credential_provider_ids: frozenset[str] = frozenset()
    licensed_provider_ids: frozenset[str] = frozenset()
    minimum_records: int = 1
    require_primary: bool = True
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchTrace:
    classification: EnergyClassification
    capability_plan: CapabilityPlan
    providers: tuple[ProviderSpec, ...]
    retrieval_outcome: RetrievalOutcome
    quality_assessment: QualityAssessment


@dataclass(frozen=True)
class ResearchResult:
    status: ResearchStatus
    answer: AnswerPacket
    trace: ResearchTrace
