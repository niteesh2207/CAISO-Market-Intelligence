from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CitationClaim:
    text: str
    source_ids: tuple[int, ...]
    claim_type: str = "fact"


@dataclass(frozen=True)
class CitationSource:
    source_id: int
    title: str
    url: str
    publisher: str
    source_tier: str


@dataclass(frozen=True)
class CitationAnswer:
    status: str
    question: str
    direct_answer: str
    explanation: str
    confidence: str
    claims: tuple[CitationClaim, ...]
    sources: tuple[CitationSource, ...]
    limitations: tuple[str, ...]
    as_of: str

    def validate(self) -> None:
        if self.status not in {
            "answered",
            "held",
        }:
            raise ValueError(
                "Invalid citation-answer status."
            )

        if self.status == "held":
            return

        if not self.direct_answer.strip():
            raise ValueError(
                "Answered responses require "
                "a direct answer."
            )

        if not self.claims:
            raise ValueError(
                "Answered responses require "
                "at least one cited claim."
            )

        if not self.sources:
            raise ValueError(
                "Answered responses require "
                "at least one source."
            )

        valid_source_ids = {
            source.source_id
            for source in self.sources
        }

        for claim in self.claims:
            if not claim.text.strip():
                raise ValueError(
                    "Claim text cannot be blank."
                )

            if not claim.source_ids:
                raise ValueError(
                    "Every factual claim requires "
                    "at least one source ID."
                )

            unknown_ids = (
                set(claim.source_ids)
                - valid_source_ids
            )

            if unknown_ids:
                raise ValueError(
                    "Claim references unknown "
                    f"source IDs: {unknown_ids}"
                )
