from market_intelligence.research.answer_quality_gate import (
    evaluate_answer,
)
from market_intelligence.research.citation_answer import (
    CitationAnswer,
    CitationClaim,
    CitationSource,
)


def test_answer_with_no_claims_fails():
    answer = CitationAnswer(
        status="answered",
        question=(
            "Where are data centers "
            "in SDG&E territory?"
        ),
        direct_answer=(
            "The EIA website provides "
            "energy information."
        ),
        explanation=(
            "It publishes reports and data."
        ),
        confidence="high",
        claims=(),
        sources=(
            CitationSource(
                source_id=1,
                title="Homepage",
                url="https://eia.gov/",
                publisher="EIA",
                source_tier="controlling",
            ),
        ),
        limitations=(),
        as_of="2026-08-05",
    )

    report = evaluate_answer(answer)

    assert report.passed is False
    assert any(
        "claim"
        in error.lower()
        for error in report.errors
    )


def test_unrelated_answer_fails_alignment():
    answer = CitationAnswer(
        status="answered",
        question=(
            "Where are data centers "
            "in SDG&E territory?"
        ),
        direct_answer=(
            "EIA publishes U.S. energy reports."
        ),
        explanation=(
            "The website contains statistics."
        ),
        confidence="medium",
        claims=(
            CitationClaim(
                text=(
                    "EIA publishes reports."
                ),
                source_ids=(1,),
            ),
        ),
        sources=(
            CitationSource(
                source_id=1,
                title="Homepage",
                url="https://eia.gov/",
                publisher="EIA",
                source_tier="controlling",
            ),
        ),
        limitations=(),
        as_of="2026-08-05",
    )

    report = evaluate_answer(answer)

    assert report.passed is False
    assert report.question_overlap < 0.35


def test_grounded_answer_passes():
    answer = CitationAnswer(
        status="answered",
        question=(
            "Where are data centers "
            "in SDG&E territory?"
        ),
        direct_answer=(
            "The available records identify "
            "data-center or large-load projects "
            "within the SDG&E service territory."
        ),
        explanation=(
            "Utility and planning documents "
            "provide the relevant locations."
        ),
        confidence="medium",
        claims=(
            CitationClaim(
                text=(
                    "The source identifies a "
                    "large-load project in SDG&E "
                    "territory."
                ),
                source_ids=(1,),
            ),
        ),
        sources=(
            CitationSource(
                source_id=1,
                title="Large Load Filing",
                url=(
                    "https://sdge.com/"
                    "large-load-filing"
                ),
                publisher="SDG&E",
                source_tier="primary",
            ),
        ),
        limitations=(
            "Public records may not identify "
            "every facility.",
        ),
        as_of="2026-08-05",
    )

    report = evaluate_answer(answer)

    assert report.passed is True


def test_alignment_normalizes_plural_and_hyphenated_terms():
    from market_intelligence.research.answer_quality_gate import (
        terms,
    )

    question_terms = terms(
        "Where are data centers "
        "in SDG&E territory?"
    )

    answer_terms = terms(
        "A data-center project is located "
        "in the SDG&E service territory."
    )

    assert "center" in question_terms
    assert "center" in answer_terms
    assert "sdgande" in question_terms
    assert "sdgande" in answer_terms
    assert "territory" in question_terms
    assert "territory" in answer_terms

