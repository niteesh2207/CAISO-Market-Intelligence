from __future__ import annotations

from market_intelligence.research.answer_quality_gate import (
    evaluate_answer,
)
from market_intelligence.research.cited_synthesizer import (
    CitedResearchAnswer,
    default_cited_synthesizer,
)
from market_intelligence.research.ddgs_provider import (
    DdgsSearchProvider,
)
from market_intelligence.research.discovery_coordinator import (
    DiscoveryCoordinator,
)
from market_intelligence.research.evidence_collector import (
    EvidenceCollector,
)
from market_intelligence.research.evidence_deduplicator import (
    deduplicate_validated_packet,
)
from market_intelligence.research.evidence_validator import (
    default_evidence_validator,
)
from market_intelligence.research.page_fetcher import (
    PageFetcher,
)
from market_intelligence.research.query_planner import (
    default_query_planner,
)


class CitedResearchService:
    def answer(
        self,
        question: str,
    ) -> CitedResearchAnswer:
        plan = default_query_planner().plan(
            question
        )

        report = DiscoveryCoordinator(
            providers=(
                DdgsSearchProvider(
                    backend="auto"
                ),
            ),
            maximum_results_per_query=8,
            maximum_candidates=24,
        ).discover(plan)

        packet = EvidenceCollector(
            fetcher=PageFetcher(
                maximum_text_characters=20_000,
            ),
            maximum_candidates_to_fetch=14,
            maximum_documents=8,
        ).collect(report)

        validated = (
            default_evidence_validator()
            .validate_packet(packet)
        )

        validated = (
            deduplicate_validated_packet(
                validated
            )
        )

        answer = (
            default_cited_synthesizer()
            .synthesize(validated)
        )

        quality = evaluate_answer(answer)

        if not quality.passed:
            raise RuntimeError(
                "Citation-answer quality gate "
                "failed: "
                + " | ".join(
                    quality.errors
                )
            )

        return answer


def default_cited_research_service(
) -> CitedResearchService:
    return CitedResearchService()
