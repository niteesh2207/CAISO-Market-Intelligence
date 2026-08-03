from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from market_intelligence.connectors.caiso_price_executor import (
    CaisoOasisPriceExecutor,
)
from market_intelligence.connectors.caiso_price_query import (
    build_caiso_price_query,
    CaisoLocation,
    CaisoMarket,
    CaisoMarketAmbiguityError,
    CaisoPriceQuery,
    resolve_caiso_location,
    resolve_caiso_market,
)
from market_intelligence.retrieval.models import (
    RetrievedRecord,
)


class CaisoPriceAgentStatus(StrEnum):
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"


class PriceExecutor(Protocol):
    def execute_to_record(
        self,
        query: CaisoPriceQuery,
        *,
        require_complete_coverage: bool = True,
    ) -> RetrievedRecord:
        ...


@dataclass(frozen=True)
class CaisoPriceAgentResult:
    status: CaisoPriceAgentStatus
    question: str
    direct_answer: str
    simple_explanation: str
    market: CaisoMarket
    location: CaisoLocation
    record: RetrievedRecord | None
    clarification_options: tuple[str, ...] = ()

    @property
    def source_url(self) -> str | None:
        if self.record is None:
            return None

        return self.record.source_url


def _market_label(
    market: CaisoMarket,
) -> str:
    labels = {
        CaisoMarket.DAY_AHEAD: "day-ahead",
        CaisoMarket.FIFTEEN_MINUTE: "fifteen-minute",
        CaisoMarket.REAL_TIME: "real-time five-minute",
        CaisoMarket.UNSPECIFIED: "unspecified",
    }

    return labels[market]


class CaisoPriceAgent:
    def __init__(
        self,
        *,
        executor: PriceExecutor | None = None,
    ) -> None:
        self.executor = (
            executor
            or CaisoOasisPriceExecutor()
        )

    def answer(
        self,
        question: str,
    ) -> CaisoPriceAgentResult:
        cleaned_question = question.strip()

        if not cleaned_question:
            raise ValueError(
                "CAISO price question cannot be empty."
            )

        location = resolve_caiso_location(
            cleaned_question
        )

        market = resolve_caiso_market(
            cleaned_question
        )

        if market == CaisoMarket.UNSPECIFIED:
            return CaisoPriceAgentResult(
                status=(
                    CaisoPriceAgentStatus
                    .NEEDS_CLARIFICATION
                ),
                question=cleaned_question,
                direct_answer=(
                    "Please specify which CAISO market "
                    "price you want."
                ),
                simple_explanation=(
                    f"{location.display_name} has separate "
                    "day-ahead, fifteen-minute and real-time "
                    "price series. They should not be combined "
                    "without an explicit comparison request."
                ),
                market=market,
                location=location,
                record=None,
                clarification_options=(
                    "Day-ahead hourly prices",
                    "Fifteen-minute prices",
                    "Real-time five-minute prices",
                    "Compare all three markets",
                ),
            )

        query = build_caiso_price_query(
            question=cleaned_question,
            location=location.display_name,
            market=market,
        )

        record = self.executor.execute_to_record(
            query,
            require_complete_coverage=True,
        )

        payload = record.payload

        direct_answer = str(
            payload.get(
                "direct_answer",
                (
                    f"{location.display_name} "
                    f"{_market_label(market)} prices "
                    "were retrieved successfully."
                ),
            )
        )

        simple_explanation = str(
            payload.get(
                "simple_explanation",
                (
                    "The result was calculated from the "
                    "complete official CAISO OASIS interval set."
                ),
            )
        )

        return CaisoPriceAgentResult(
            status=CaisoPriceAgentStatus.ANSWERED,
            question=cleaned_question,
            direct_answer=direct_answer,
            simple_explanation=simple_explanation,
            market=market,
            location=location,
            record=record,
        )
