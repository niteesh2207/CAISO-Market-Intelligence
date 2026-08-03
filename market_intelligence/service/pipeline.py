from __future__ import annotations

from market_intelligence.answers.composer import (
    compose_answer_packet,
)
from market_intelligence.answers.models import (
    AnswerSource,
)
from market_intelligence.connectors.catalog import (
    matching_providers,
)
from market_intelligence.quality.gate import (
    assess_evidence_quality,
)
from market_intelligence.quality.models import (
    ReleaseDecision,
)
from market_intelligence.retrieval.orchestrator import (
    RetrievalOrchestrator,
    Retriever,
)
from market_intelligence.routing.capability_router import (
    route_capabilities,
)
from market_intelligence.routing.energy_parser import (
    classify_energy_question,
)
from market_intelligence.service.answer_builder import (
    AnswerDraftBuilder,
    default_answer_draft_builder,
)
from market_intelligence.service.evidence import (
    quality_input_from_retrieval,
)
from market_intelligence.service.models import (
    ResearchRequest,
    ResearchResult,
    ResearchStatus,
    ResearchTrace,
)


class EnergyResearchService:
    def __init__(
        self,
        *,
        retriever: Retriever,
        answer_builder: AnswerDraftBuilder | None = None,
    ) -> None:
        self.orchestrator = RetrievalOrchestrator(
            retriever
        )
        self.answer_builder = (
            answer_builder
            or default_answer_draft_builder
        )

    def research(
        self,
        request: ResearchRequest,
    ) -> ResearchResult:
        question = request.question.strip()

        if not question:
            raise ValueError(
                "Research question cannot be empty."
            )

        classification = classify_energy_question(
            question
        )

        capability_plan = route_capabilities(
            classification
        )

        providers = matching_providers(
            classification,
            capability_plan,
            include_licensed=bool(
                request.licensed_provider_ids
            ),
        )

        retrieval_outcome = self.orchestrator.retrieve(
            providers=providers,
            request={
                "question": question,
                "classification": classification,
                "capability_plan": capability_plan,
                "context": request.context,
            },
            credential_provider_ids=set(
                request.credential_provider_ids
            ),
            licensed_provider_ids=set(
                request.licensed_provider_ids
            ),
            minimum_records=request.minimum_records,
            require_primary=request.require_primary,
        )

        quality_input = quality_input_from_retrieval(
            retrieval_outcome,
            complete_coverage=request.context.get(
                "complete_coverage"
            ),
            has_unit=request.context.get(
                "has_unit"
            ),
            has_market_context=request.context.get(
                "has_market_context"
            ),
            has_timezone=request.context.get(
                "has_timezone"
            ),
            calculation_verified=request.context.get(
                "calculation_verified",
                True,
            ),
            has_source_conflict=request.context.get(
                "has_source_conflict",
                False,
            ),
        )

        quality_assessment = assess_evidence_quality(
            quality_input,
            claim_type=request.claim_type,
        )

        draft = self.answer_builder(
            question,
            classification,
            retrieval_outcome.records,
            request.claim_type,
            request.context,
        )

        answer_sources = [
            AnswerSource(
                source_id=f"source-{index + 1}",
                provider_id=record.provider_id,
                title=record.source_title,
                url=record.source_url,
                is_primary=record.is_primary,
                authority_rank=record.authority_rank,
                observed_at=record.observed_at,
                published_at=record.published_at,
                retrieved_at=record.retrieved_at,
            )
            for index, record in enumerate(
                retrieval_outcome.records
            )
        ]

        limitations = list(
            draft.limitations
        )
        limitations.extend(
            retrieval_outcome.warnings
        )

        blocked_decisions = {
            ReleaseDecision.HOLD,
            ReleaseDecision.REFUSE_NUMERIC_CLAIM,
        }

        if (
            quality_assessment.decision
            in blocked_decisions
        ):
            # Evidence that fails the release gate must never be
            # repackaged as a normal factual or numerical claim.
            #
            # Retain the source trail for auditability, but remove
            # unsafe claims and replace the answer text with a
            # controlled explanation.
            claims_for_packet = []

            if (
                quality_assessment.decision
                == ReleaseDecision.REFUSE_NUMERIC_CLAIM
            ):
                direct_answer = (
                    "The exact numerical answer cannot be "
                    "verified from the available evidence."
                )
                simple_explanation = (
                    "A value was retrieved, but one or more "
                    "mandatory controls?such as unit, market, "
                    "timestamp, timezone or calculation "
                    "verification?were missing."
                )
            else:
                direct_answer = (
                    "The requested answer cannot currently be "
                    "confirmed."
                )
                simple_explanation = (
                    "The available evidence did not satisfy the "
                    "configured release requirements."
                )

            if (
                quality_assessment.rationale
                not in limitations
            ):
                limitations.append(
                    quality_assessment.rationale
                )

        else:
            claims_for_packet = list(
                draft.claims
            )
            direct_answer = draft.direct_answer
            simple_explanation = (
                draft.simple_explanation
            )

        answer = compose_answer_packet(
            question=question,
            direct_answer=direct_answer,
            simple_explanation=simple_explanation,
            claims=claims_for_packet,
            sources=answer_sources,
            quality_assessment=quality_assessment,
            additional_limitations=limitations,
        )

        if (
            quality_assessment.decision
            == ReleaseDecision.RELEASE
        ):
            status = ResearchStatus.ANSWERED

        elif (
            quality_assessment.decision
            == ReleaseDecision.RELEASE_WITH_WARNING
        ):
            status = (
                ResearchStatus.ANSWERED_WITH_WARNING
            )

        else:
            status = ResearchStatus.HELD

        trace = ResearchTrace(
            classification=classification,
            capability_plan=capability_plan,
            providers=tuple(providers),
            retrieval_outcome=retrieval_outcome,
            quality_assessment=quality_assessment,
        )

        return ResearchResult(
            status=status,
            answer=answer,
            trace=trace,
        )
