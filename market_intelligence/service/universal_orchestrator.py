from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import os
import re
from typing import Any, Protocol


from market_intelligence.routing.universal_energy_router import (
    EnergyDomain,
    UniversalEnergyRoute,
    route_energy_question,
)


class UniversalAnswerStatus(StrEnum):
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    RESEARCH_REQUIRED = "research_required"
    HELD = "held"


@dataclass(frozen=True)
class UniversalSource:
    title: str
    url: str
    provider_id: str
    is_primary: bool
    source_role: str = "controlling"


@dataclass(frozen=True)
class UniversalAnswer:
    question: str
    status: UniversalAnswerStatus
    domain: EnergyDomain
    direct_answer: str
    simple_explanation: str
    confidence: str
    sources: tuple[UniversalSource, ...] = ()
    limitations: tuple[str, ...] = ()
    clarification_options: tuple[str, ...] = ()
    route: UniversalEnergyRoute | None = None
    evidence_payload: dict[str, Any] = field(
        default_factory=dict
    )


class CaisoAgentProtocol(Protocol):
    def answer(self, question: str) -> Any:
        ...


class NuclearAgentProtocol(Protocol):
    def answer(self, question: str) -> Any:
        ...


class OperatingDataAgentProtocol(Protocol):
    def answer(self, question: str) -> Any:
        ...


class ResearchAgentProtocol(Protocol):
    def answer(self, question: str) -> Any:
        ...


def _source_from_record(
    record: Any,
    *,
    source_role: str = "controlling",
) -> UniversalSource:
    return UniversalSource(
        title=str(record.source_title),
        url=str(record.source_url),
        provider_id=str(record.provider_id),
        is_primary=bool(record.is_primary),
        source_role=source_role,
    )


def _research_plan_explanation(
    route: UniversalEnergyRoute,
) -> str:
    providers = ", ".join(
        provider.provider_id
        for provider in route.providers
    )

    if not providers:
        providers = "no approved providers resolved"

    return (
        f"This question was routed to the "
        f"{route.domain.value} research pathway. "
        f"The preferred evidence sequence is: {providers}. "
        "A numerical or factual claim will not be published "
        "until the required source executors return "
        "validated evidence."
    )


def _extract_nuclear_asset(
    question: str,
    route: UniversalEnergyRoute,
) -> str | None:
    entity_map = {
        "diablo canyon": "Diablo Canyon",
        "palo verde": "Palo Verde",
    }

    for entity in route.matched_entities:
        normalized = entity.lower().strip()

        if normalized in entity_map:
            return entity_map[normalized]

    normalized_question = question.lower()

    for normalized, display in entity_map.items():
        if normalized in normalized_question:
            return display

    return None


class DefaultNuclearAgent:
    """Live NRC reactor-status adapter."""

    def answer(
        self,
        question: str,
    ) -> UniversalAnswer:
        from market_intelligence.connectors.catalog import (
            provider_by_id,
        )
        from market_intelligence.connectors.nrc_reactor_status import (
            answer_to_retrieved_record,
            NrcReactorStatusConnector,
        )

        route = route_energy_question(question)
        asset = _extract_nuclear_asset(
            question,
            route,
        )

        if asset is None:
            return UniversalAnswer(
                question=question,
                status=(
                    UniversalAnswerStatus
                    .NEEDS_CLARIFICATION
                ),
                domain=EnergyDomain.NUCLEAR,
                direct_answer=(
                    "Please specify the nuclear plant "
                    "or reactor unit."
                ),
                simple_explanation=(
                    "The NRC status executor needs a "
                    "specific plant or unit name."
                ),
                confidence="insufficient",
                clarification_options=(
                    "Specify the plant name",
                    "Specify the reactor unit",
                ),
                route=route,
            )

        provider = provider_by_id(
            "nrc_reactor_status"
        )

        if provider is None:
            return UniversalAnswer(
                question=question,
                status=UniversalAnswerStatus.HELD,
                domain=EnergyDomain.NUCLEAR,
                direct_answer=(
                    "The NRC provider is not available."
                ),
                simple_explanation=(
                    "The answer was held because the "
                    "controlling reactor-status source "
                    "could not be initialized."
                ),
                confidence="insufficient",
                limitations=(
                    "NRC provider configuration unavailable.",
                ),
                route=route,
            )

        connector = NrcReactorStatusConnector()

        report = connector.fetch_report(
            provider=provider
        )

        answer = connector.answer_plant_status(
            report=report,
            plant_query=asset,
            question=question,
        )

        record = answer_to_retrieved_record(
            answer
        )

        return UniversalAnswer(
            question=question,
            status=UniversalAnswerStatus.ANSWERED,
            domain=EnergyDomain.NUCLEAR,
            direct_answer=answer.direct_answer,
            simple_explanation=(
                answer.simple_explanation
            ),
            confidence="high",
            sources=(
                _source_from_record(record),
            ),
            route=route,
            evidence_payload=dict(record.payload),
        )


class UniversalResearchOrchestrator:
    def __init__(
        self,
        *,
        caiso_agent: CaisoAgentProtocol | None = None,
        nuclear_agent: NuclearAgentProtocol | None = None,
        operating_data_agent: (
            OperatingDataAgentProtocol | None
        ) = None,
        research_agent: (
            ResearchAgentProtocol | None
        ) = None,
    ) -> None:
        self._caiso_agent = caiso_agent
        self._nuclear_agent = nuclear_agent
        self._operating_data_agent = (
            operating_data_agent
        )
        self._research_agent = research_agent

    @property
    def caiso_agent(self) -> CaisoAgentProtocol:
        if self._caiso_agent is None:
            from market_intelligence.service.caiso_price_agent import (
                CaisoPriceAgent,
            )

            self._caiso_agent = CaisoPriceAgent()

        return self._caiso_agent

    @property
    def nuclear_agent(self) -> NuclearAgentProtocol:
        if self._nuclear_agent is None:
            self._nuclear_agent = DefaultNuclearAgent()

        return self._nuclear_agent

    @property
    def operating_data_agent(
        self,
    ) -> OperatingDataAgentProtocol:
        if self._operating_data_agent is None:
            from market_intelligence.service.eia_operating_data_agent import (
                EiaOperatingDataAgent,
            )

            self._operating_data_agent = (
                EiaOperatingDataAgent()
            )

        return self._operating_data_agent

    @property
    def research_agent(
        self,
    ) -> ResearchAgentProtocol:
        if self._research_agent is None:
            from market_intelligence.research.free_research_agent import (
                FreeResearchAgent,
            )
            from market_intelligence.research.gdelt_client import (
                GdeltClient,
            )
            from market_intelligence.research.ollama_client import (
                OllamaClient,
            )
            from market_intelligence.research.page_fetcher import (
                PageFetcher,
            )

            model = os.getenv(
                "OLLAMA_MODEL",
                "gemma3:4b",
            ).strip()

            if not model:
                model = "gemma3:4b"

            self._research_agent = FreeResearchAgent(
                gdelt=GdeltClient(),
                fetcher=PageFetcher(),
                ollama=OllamaClient(
                    model=model,
                ),
            )

        return self._research_agent

    def answer(
        self,
        question: str,
    ) -> UniversalAnswer:
        cleaned = question.strip()

        if not cleaned:
            raise ValueError(
                "Energy question cannot be empty."
            )

        route = route_energy_question(cleaned)

        if route.domain == EnergyDomain.UNKNOWN:
            return UniversalAnswer(
                question=cleaned,
                status=(
                    UniversalAnswerStatus
                    .NEEDS_CLARIFICATION
                ),
                domain=route.domain,
                direct_answer=(
                    route.clarification
                    or "Please provide an energy question."
                ),
                simple_explanation=(
                    "The query could not be mapped to an "
                    "energy-market, fuel, asset, grid, "
                    "weather or regulatory research path."
                ),
                confidence="insufficient",
                route=route,
            )

        if route.domain == EnergyDomain.NUCLEAR:
            result = self.nuclear_agent.answer(
                cleaned
            )

            if isinstance(result, UniversalAnswer):
                return result

            raise TypeError(
                "Nuclear agent returned an unsupported "
                "answer type."
            )

        if (
            route.domain
            == EnergyDomain.ELECTRICITY_MARKETS
            and self._is_operating_data_question(
                cleaned
            )
        ):
            return self._answer_operating_data(
                cleaned,
                route,
            )

        if (
            route.domain
            == EnergyDomain.ELECTRICITY_MARKETS
            and route.geography == "california"
        ):
            return self._answer_caiso(
                cleaned,
                route,
            )

        return self._answer_research(
            cleaned,
            route,
        )

    def _answer_research(
        self,
        question: str,
        route: UniversalEnergyRoute,
    ) -> UniversalAnswer:
        try:
            result = self.research_agent.answer(
                question
            )
        except Exception as exc:
            return UniversalAnswer(
                question=question,
                status=UniversalAnswerStatus.HELD,
                domain=route.domain,
                direct_answer=(
                    "The research answer could not be "
                    "completed from verified evidence."
                ),
                simple_explanation=(
                    "The question was classified as an "
                    "energy question, but the free research "
                    "pipeline encountered a retrieval or "
                    "synthesis failure."
                ),
                confidence="insufficient",
                limitations=(
                    f"Research pipeline failure: "
                    f"{type(exc).__name__}: {exc}",
                ),
                route=route,
                evidence_payload={
                    "planned_providers": [
                        provider.provider_id
                        for provider in route.providers
                    ],
                    "research_exception": (
                        type(exc).__name__
                    ),
                },
            )

        result_status = str(
            getattr(
                getattr(result, "status", None),
                "value",
                getattr(result, "status", ""),
            )
        )

        sources = tuple(
            UniversalSource(
                title=str(source.title),
                url=str(source.url),
                provider_id=str(
                    source.provider
                ),
                is_primary=bool(
                    source.primary
                ),
                source_role=str(
                    getattr(
                        getattr(
                            source,
                            "source_tier",
                            "",
                        ),
                        "value",
                        getattr(
                            source,
                            "source_tier",
                            "supporting",
                        ),
                    )
                ),
            )
            for source in getattr(
                result,
                "sources",
                (),
            )
        )

        evidence_payload = dict(
            getattr(
                result,
                "evidence",
                {},
            )
        )

        evidence_payload.update(
            {
                "research_as_of": str(
                    getattr(
                        result,
                        "as_of",
                        "",
                    )
                ),
                "planned_providers": [
                    {
                        "provider_id": (
                            provider.provider_id
                        ),
                        "priority": (
                            provider.priority
                        ),
                        "source_role": (
                            provider.source_role
                        ),
                        "retrieval_modes": list(
                            provider.retrieval_modes
                        ),
                    }
                    for provider in route.providers
                ],
            }
        )

        if result_status == "answered":
            return UniversalAnswer(
                question=question,
                status=UniversalAnswerStatus.ANSWERED,
                domain=route.domain,
                direct_answer=str(
                    result.answer
                ),
                simple_explanation=str(
                    result.explanation
                ),
                confidence=str(
                    result.confidence
                ),
                sources=sources,
                limitations=tuple(
                    str(item)
                    for item in result.limitations
                ),
                route=route,
                evidence_payload=evidence_payload,
            )

        return UniversalAnswer(
            question=question,
            status=UniversalAnswerStatus.HELD,
            domain=route.domain,
            direct_answer=str(
                getattr(
                    result,
                    "answer",
                    (
                        "The research pipeline could not "
                        "verify an answer."
                    ),
                )
            ),
            simple_explanation=str(
                getattr(
                    result,
                    "explanation",
                    _research_plan_explanation(route),
                )
            ),
            confidence="insufficient",
            sources=sources,
            limitations=tuple(
                str(item)
                for item in getattr(
                    result,
                    "limitations",
                    (),
                )
            ),
            route=route,
            evidence_payload=evidence_payload,
        )

    @staticmethod
    def _is_operating_data_question(
        question: str,
    ) -> bool:
        from market_intelligence.service.eia_operating_data_agent import (
            resolve_authority,
            resolve_metric,
        )

        return (
            resolve_authority(question) is not None
            and resolve_metric(question) is not None
        )

    def _answer_operating_data(
        self,
        question: str,
        route: UniversalEnergyRoute,
    ) -> UniversalAnswer:
        from market_intelligence.service.eia_operating_data_agent import (
            OperatingDataStatus,
        )

        result = self.operating_data_agent.answer(
            question
        )

        status_value = str(
            getattr(
                getattr(result, "status", None),
                "value",
                getattr(result, "status", ""),
            )
        )

        if (
            status_value
            == OperatingDataStatus
            .NEEDS_CLARIFICATION
            .value
        ):
            return UniversalAnswer(
                question=question,
                status=(
                    UniversalAnswerStatus
                    .NEEDS_CLARIFICATION
                ),
                domain=route.domain,
                direct_answer=str(
                    result.direct_answer
                ),
                simple_explanation=str(
                    result.simple_explanation
                ),
                confidence="insufficient",
                limitations=(
                    "The balancing authority or "
                    "operating metric was ambiguous.",
                ),
                route=route,
            )

        if status_value not in {
            OperatingDataStatus.ANSWERED.value,
            OperatingDataStatus.STALE.value,
        }:
            return UniversalAnswer(
                question=question,
                status=UniversalAnswerStatus.HELD,
                domain=route.domain,
                direct_answer=(
                    "The operating-data answer was held."
                ),
                simple_explanation=(
                    "The EIA executor did not return "
                    "a releasable operating-data result."
                ),
                confidence="insufficient",
                limitations=(
                    "Unsupported EIA operating-data status.",
                ),
                route=route,
            )

        if (
            result.value is None
            or result.source_unit is None
            or result.observation_timestamp_utc is None
            or not result.source_url
        ):
            return UniversalAnswer(
                question=question,
                status=UniversalAnswerStatus.HELD,
                domain=route.domain,
                direct_answer=(
                    "The operating-data answer was held."
                ),
                simple_explanation=(
                    "Mandatory numerical evidence "
                    "controls were incomplete."
                ),
                confidence="insufficient",
                limitations=(
                    "Missing value, unit, timestamp "
                    "or official source URL.",
                ),
                route=route,
            )

        stale = (
            status_value
            == OperatingDataStatus.STALE.value
        )

        source = UniversalSource(
            title=(
                "EIA U.S. Electric System "
                "Operating Data"
            ),
            url=str(result.source_url),
            provider_id="eia_bulk_eba",
            is_primary=True,
            source_role="controlling",
        )

        limitations = ()

        if stale:
            limitations = (
                "The latest available observation "
                "exceeded the configured freshness "
                "threshold.",
            )

        return UniversalAnswer(
            question=question,
            status=UniversalAnswerStatus.ANSWERED,
            domain=route.domain,
            direct_answer=str(
                result.direct_answer
            ),
            simple_explanation=str(
                result.simple_explanation
            ),
            confidence=(
                "medium"
                if stale
                else "high"
            ),
            sources=(source,),
            limitations=limitations,
            route=route,
            evidence_payload={
                "balancing_authority": (
                    result.balancing_authority
                ),
                "metric": (
                    result.metric.value
                    if result.metric is not None
                    else None
                ),
                "value": result.value,
                "source_unit": result.source_unit,
                "equivalent_average_mw": (
                    result.equivalent_average_mw
                ),
                "observation_timestamp_utc": (
                    result
                    .observation_timestamp_utc
                    .isoformat()
                ),
                "age_hours": result.age_hours,
                "stale": stale,
            },
        )

    def _answer_caiso(
        self,
        question: str,
        route: UniversalEnergyRoute,
    ) -> UniversalAnswer:
        result = self.caiso_agent.answer(
            question
        )

        status_value = str(
            getattr(
                getattr(result, "status", None),
                "value",
                getattr(result, "status", ""),
            )
        )

        if status_value == "needs_clarification":
            return UniversalAnswer(
                question=question,
                status=(
                    UniversalAnswerStatus
                    .NEEDS_CLARIFICATION
                ),
                domain=route.domain,
                direct_answer=str(
                    result.direct_answer
                ),
                simple_explanation=str(
                    result.simple_explanation
                ),
                confidence="insufficient",
                clarification_options=tuple(
                    result.clarification_options
                ),
                route=route,
            )

        record = getattr(
            result,
            "record",
            None,
        )

        if record is None:
            return UniversalAnswer(
                question=question,
                status=UniversalAnswerStatus.HELD,
                domain=route.domain,
                direct_answer=(
                    "The CAISO price answer was held."
                ),
                simple_explanation=(
                    "The market executor did not return "
                    "a validated evidence record."
                ),
                confidence="insufficient",
                limitations=(
                    "Missing CAISO evidence record.",
                ),
                route=route,
            )

        if not bool(record.is_primary):
            return UniversalAnswer(
                question=question,
                status=UniversalAnswerStatus.HELD,
                domain=route.domain,
                direct_answer=(
                    "The CAISO price answer was held."
                ),
                simple_explanation=(
                    "The result was not attributed to a "
                    "controlling primary source."
                ),
                confidence="insufficient",
                limitations=(
                    "CAISO evidence was not marked primary.",
                ),
                route=route,
            )

        payload = dict(record.payload)

        if not payload.get(
            "complete_coverage",
            False,
        ):
            return UniversalAnswer(
                question=question,
                status=UniversalAnswerStatus.HELD,
                domain=route.domain,
                direct_answer=(
                    "The CAISO price answer was held."
                ),
                simple_explanation=(
                    "The official result did not contain "
                    "complete interval coverage."
                ),
                confidence="insufficient",
                limitations=(
                    "Incomplete CAISO market-day coverage.",
                ),
                route=route,
            )

        return UniversalAnswer(
            question=question,
            status=UniversalAnswerStatus.ANSWERED,
            domain=route.domain,
            direct_answer=str(
                result.direct_answer
            ),
            simple_explanation=str(
                result.simple_explanation
            ),
            confidence="high",
            sources=(
                _source_from_record(record),
            ),
            route=route,
            evidence_payload=payload,
        )
