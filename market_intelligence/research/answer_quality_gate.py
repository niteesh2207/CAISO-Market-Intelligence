from __future__ import annotations

import re
from dataclasses import dataclass

from market_intelligence.research.citation_answer import (
    CitationAnswer,
)


STOPWORDS = {
    "about",
    "after",
    "are",
    "can",
    "data",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "latest",
    "of",
    "the",
    "their",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "with",
}


@dataclass(frozen=True)
class AnswerQualityReport:
    passed: bool
    errors: tuple[str, ...]
    question_overlap: float


def normalize_term(
    token: str,
) -> str:
    normalized = (
        token.lower()
        .strip("._-")
        .replace("&", "and")
    )

    # Normalize common singular/plural forms without
    # adding a heavy NLP dependency.
    if (
        len(normalized) > 4
        and normalized.endswith("ies")
    ):
        normalized = (
            normalized[:-3] + "y"
        )
    elif (
        len(normalized) > 4
        and normalized.endswith("s")
        and not normalized.endswith("ss")
    ):
        normalized = normalized[:-1]

    return normalized


def terms(value: str) -> set[str]:
    expanded = value.lower().replace(
        "-",
        " ",
    )

    tokens = re.findall(
        r"[a-z0-9][a-z0-9&.]{1,}",
        expanded,
    )

    return {
        normalized
        for token in tokens
        if (
            normalized := normalize_term(
                token
            )
        )
        and len(normalized) >= 3
        and normalized not in STOPWORDS
    }


def evaluate_answer(
    answer: CitationAnswer,
) -> AnswerQualityReport:
    errors: list[str] = []

    try:
        answer.validate()
    except ValueError as exc:
        errors.append(str(exc))

    if answer.status == "held":
        return AnswerQualityReport(
            passed=not errors,
            errors=tuple(errors),
            question_overlap=0.0,
        )

    question_terms = terms(
        answer.question
    )

    answer_terms = terms(
        " ".join(
            (
                answer.direct_answer,
                answer.explanation,
            )
        )
    )

    overlap = (
        len(
            question_terms
            & answer_terms
        )
        / max(
            len(question_terms),
            1,
        )
    )

    if overlap < 0.35:
        errors.append(
            "The generated answer does not "
            "sufficiently address the question."
        )

    unique_urls = {
        source.url
        for source in answer.sources
    }

    if len(unique_urls) != len(
        answer.sources
    ):
        errors.append(
            "Duplicate sources are present."
        )

    cited_ids = {
        source_id
        for claim in answer.claims
        for source_id in claim.source_ids
    }

    available_ids = {
        source.source_id
        for source in answer.sources
    }

    if not cited_ids:
        errors.append(
            "No source IDs were cited."
        )

    if not cited_ids.issubset(
        available_ids
    ):
        errors.append(
            "One or more claims reference "
            "invalid source IDs."
        )

    return AnswerQualityReport(
        passed=not errors,
        errors=tuple(errors),
        question_overlap=round(
            overlap,
            3,
        ),
    )
