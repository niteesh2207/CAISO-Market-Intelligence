from market_intelligence.research.answer_quality_gate import (
    evaluate_answer,
)
from market_intelligence.research.cited_synthesizer import (
    CitedClaim,
    CitedResearchAnswer,
    CitedSource,
)


def test_cited_research_answer_passes_quality_gate():
    answer = CitedResearchAnswer(
        status="answered",
        question=(
            "Where are data centers "
            "in SDG&E territory?"
        ),
        direct_answer=(
            "The available evidence identifies "
            "a data-center project within "
            "SDG&E territory."
        ),
        explanation=(
            "The cited utility filing connects "
            "the project to the SDG&E service area."
        ),
        confidence="medium",
        as_of="2026-08-05T16:00:00+00:00",
        claims=(
            CitedClaim(
                text=(
                    "A data-center project is "
                    "identified in SDG&E territory."
                ),
                source_ids=(1,),
                claim_type="fact",
            ),
        ),
        sources=(
            CitedSource(
                source_id=1,
                title="Large Load Filing",
                url=(
                    "https://www.sdge.com/"
                    "large-load-filing"
                ),
                provider="SDG&E",
                source_tier="primary",
                retrieved_at=(
                    "2026-08-05T15:00:00+00:00"
                ),
            ),
        ),
        limitations=(
            "Public records may not identify "
            "every facility.",
        ),
        evidence_summary={
            "accepted_documents": 1,
            "rejected_documents": 0,
            "validation_failures": 0,
            "cited_claims": 1,
        },
    )

    answer.validate()

    report = evaluate_answer(answer)

    assert report.passed is True
    assert report.errors == ()
    assert report.question_overlap >= 0.35


def test_cited_research_answer_rejects_unknown_source():
    answer = CitedResearchAnswer(
        status="answered",
        question="What is CAISO demand?",
        direct_answer=(
            "CAISO demand is reported by "
            "the cited source."
        ),
        explanation=(
            "The response relies on operating data."
        ),
        confidence="medium",
        as_of="2026-08-05T16:00:00+00:00",
        claims=(
            CitedClaim(
                text="CAISO demand was reported.",
                source_ids=(2,),
                claim_type="fact",
            ),
        ),
        sources=(
            CitedSource(
                source_id=1,
                title="EIA Operating Data",
                url=(
                    "https://www.eia.gov/"
                    "opendata/bulk/EBA.zip"
                ),
                provider="EIA",
                source_tier="controlling",
                retrieved_at=(
                    "2026-08-05T15:00:00+00:00"
                ),
            ),
        ),
        limitations=(),
        evidence_summary={},
    )

    try:
        answer.validate()
    except ValueError as exc:
        assert "unknown source IDs" in str(exc)
    else:
        raise AssertionError(
            "Unknown source ID was not rejected."
        )
