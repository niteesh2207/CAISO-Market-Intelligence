from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.request import Request, urlopen

from market_intelligence.research.evidence_validator import (
    ValidatedEvidencePacket,
)


class CitedSynthesisError(RuntimeError):
    pass


HttpPost = Callable[
    [str, bytes, dict[str, str], float],
    bytes,
]


def default_http_post(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
) -> bytes:
    request = Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )

    with urlopen(
        request,
        timeout=timeout,
    ) as response:
        return response.read()


@dataclass(frozen=True)
class CitedClaim:
    text: str
    source_ids: tuple[int, ...]
    claim_type: str


@dataclass(frozen=True)
class CitedSource:
    source_id: int
    title: str
    url: str
    provider: str
    source_tier: str
    retrieved_at: str


@dataclass(frozen=True)
class CitedResearchAnswer:
    status: str
    direct_answer: str
    explanation: str
    confidence: str
    as_of: str
    claims: tuple[CitedClaim, ...]
    sources: tuple[CitedSource, ...]
    limitations: tuple[str, ...]
    evidence_summary: dict[str, Any]
    question: str = ""

    def validate(self) -> None:
        if self.status not in {
            "answered",
            "held",
        }:
            raise ValueError(
                "Invalid cited-answer status."
            )

        if not self.question.strip():
            raise ValueError(
                "The original question is missing."
            )

        if self.status == "held":
            return

        if not self.direct_answer.strip():
            raise ValueError(
                "Answered responses require "
                "a direct answer."
            )

        if not self.explanation.strip():
            raise ValueError(
                "Answered responses require "
                "an explanation."
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

            if (
                claim.claim_type == "fact"
                and not claim.source_ids
            ):
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


ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "direct_answer": {
            "type": "string",
        },
        "explanation": {
            "type": "string",
        },
        "confidence": {
            "type": "string",
            "enum": [
                "high",
                "medium",
                "low",
                "insufficient",
            ],
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                    },
                    "source_ids": {
                        "type": "array",
                        "items": {
                            "type": "integer",
                            "minimum": 1,
                        },
                    },
                    "claim_type": {
                        "type": "string",
                        "enum": [
                            "fact",
                            "inference",
                            "context",
                        ],
                    },
                },
                "required": [
                    "text",
                    "source_ids",
                    "claim_type",
                ],
                "additionalProperties": False,
            },
        },
        "limitations": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
    },
    "required": [
        "direct_answer",
        "explanation",
        "confidence",
        "claims",
        "limitations",
    ],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """
You are a senior energy-market research analyst.

Answer the user's question using only the supplied validated evidence.

Rules:

1. Do not use outside knowledge.
2. Do not invent names, locations, dates, capacities or market facts.
3. Every material factual claim must reference at least one valid
   source ID.
4. Use the source IDs exactly as supplied.
5. Clearly distinguish facts from inferences.
6. Do not claim that a list is exhaustive unless the evidence proves
   that it is exhaustive.
7. If the sources provide only partial evidence, give the strongest
   supported partial answer and explain the limitation.
8. Directly answer the question before providing explanation.
9. Keep the answer readable and commercially useful.
10. Never cite a source that does not support the corresponding claim.

Return only the requested JSON structure.
""".strip()


@dataclass(frozen=True)
class OllamaCitedSynthesizer:
    model: str = "gemma3:4b"
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 240.0
    http_post: HttpPost = default_http_post

    @staticmethod
    def _evidence_text(
        packet: ValidatedEvidencePacket,
    ) -> str:
        blocks: list[str] = []

        for index, item in enumerate(
            packet.documents,
            start=1,
        ):
            document = item.document

            supported_claims = "\n".join(
                f"- {claim}"
                for claim in item.supported_claims
            ) or "- None explicitly extracted"

            blocks.append(
                "\n".join(
                    (
                        f"SOURCE_ID: {index}",
                        f"TITLE: {document.title}",
                        f"PROVIDER: {document.provider}",
                        f"URL: {document.url}",
                        (
                            "SOURCE_TIER: "
                            f"{document.source_tier}"
                        ),
                        (
                            "SEMANTIC_SCOPE: "
                            f"{item.source_scope}"
                        ),
                        (
                            "SEMANTIC_SCORE: "
                            f"{item.semantic_relevance_score}"
                        ),
                        "VALIDATED_SUPPORTED_CLAIMS:",
                        supported_claims,
                        "SOURCE_TEXT:",
                        document.text[:10_000],
                    )
                )
            )

        return "\n\n".join(blocks)

    def _held_answer(
        self,
        packet: ValidatedEvidencePacket,
    ) -> CitedResearchAnswer:
        limitations = [
            packet.sufficiency_reason,
        ]

        limitations.extend(
            failure.error
            for failure in (
                packet.validation_failures
            )
        )

        return CitedResearchAnswer(
            status="held",
            question=packet.question,
            direct_answer=(
                "The available verified evidence "
                "is not sufficient to provide a "
                "reliable answer."
            ),
            explanation=(
                "The research system retrieved and "
                "reviewed sources, but none provided "
                "enough direct, answerable evidence "
                "to support a factual conclusion."
            ),
            confidence="insufficient",
            as_of=datetime.now(
                timezone.utc
            ).isoformat(),
            claims=(),
            sources=(),
            limitations=tuple(
                dict.fromkeys(limitations)
            ),
            evidence_summary={
                "accepted_documents": len(
                    packet.documents
                ),
                "rejected_documents": len(
                    packet.rejected_documents
                ),
                "validation_failures": len(
                    packet.validation_failures
                ),
            },
        )

    def synthesize(
        self,
        packet: ValidatedEvidencePacket,
    ) -> CitedResearchAnswer:
        if not packet.sufficient:
            return self._held_answer(
                packet
            )

        if not packet.documents:
            return self._held_answer(
                packet
            )

        evidence_text = self._evidence_text(
            packet
        )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        f"QUESTION:\n"
                        f"{packet.question}\n\n"
                        f"VALIDATED EVIDENCE:\n"
                        f"{evidence_text}"
                    ),
                },
            ],
            "format": ANSWER_SCHEMA,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 1_800,
                "top_k": 20,
                "top_p": 0.8,
            },
        }

        try:
            raw = self.http_post(
                (
                    self.base_url.rstrip("/")
                    + "/api/chat"
                ),
                json.dumps(
                    payload,
                    ensure_ascii=False,
                ).encode("utf-8"),
                {
                    "Content-Type": (
                        "application/json"
                    ),
                    "Accept": "application/json",
                },
                self.timeout_seconds,
            )

            envelope = json.loads(
                raw.decode(
                    "utf-8",
                    errors="replace",
                )
            )

            content = str(
                envelope.get(
                    "message",
                    {},
                ).get(
                    "content",
                    "",
                )
            ).strip()

            if not content:
                raise CitedSynthesisError(
                    "Ollama returned an empty "
                    "synthesis response."
                )

            result = json.loads(content)

        except Exception as exc:
            raise CitedSynthesisError(
                f"Cited synthesis failed: {exc}"
            ) from exc

        maximum_source_id = len(
            packet.documents
        )

        claims: list[CitedClaim] = []

        for item in result["claims"]:
            source_ids = tuple(
                dict.fromkeys(
                    int(source_id)
                    for source_id in item[
                        "source_ids"
                    ]
                    if (
                        1
                        <= int(source_id)
                        <= maximum_source_id
                    )
                )
            )

            claim_type = str(
                item["claim_type"]
            ).strip().lower()

            if claim_type not in {
                "fact",
                "inference",
                "context",
            }:
                claim_type = "context"

            if (
                claim_type == "fact"
                and not source_ids
            ):
                continue

            claims.append(
                CitedClaim(
                    text=str(
                        item["text"]
                    ).strip(),
                    source_ids=source_ids,
                    claim_type=claim_type,
                )
            )

        sources = tuple(
            CitedSource(
                source_id=index,
                title=item.document.title,
                url=item.document.url,
                provider=(
                    item.document.provider
                ),
                source_tier=(
                    item.document.source_tier
                ),
                retrieved_at=(
                    item.document.retrieved_at
                ),
            )
            for index, item in enumerate(
                packet.documents,
                start=1,
            )
        )

        confidence = str(
            result["confidence"]
        ).strip().lower()

        if confidence not in {
            "high",
            "medium",
            "low",
            "insufficient",
        }:
            confidence = "low"

        limitations = [
            str(item).strip()
            for item in result.get(
                "limitations",
                (),
            )
            if str(item).strip()
        ]

        limitations.extend(
            item
            for document in packet.documents
            for item in (
                document.missing_information
            )
            if item
        )

        return CitedResearchAnswer(
            status="answered",
            question=packet.question,
            direct_answer=str(
                result["direct_answer"]
            ).strip(),
            explanation=str(
                result["explanation"]
            ).strip(),
            confidence=confidence,
            as_of=datetime.now(
                timezone.utc
            ).isoformat(),
            claims=tuple(claims),
            sources=sources,
            limitations=tuple(
                dict.fromkeys(limitations)
            ),
            evidence_summary={
                "accepted_documents": len(
                    packet.documents
                ),
                "rejected_documents": len(
                    packet.rejected_documents
                ),
                "validation_failures": len(
                    packet.validation_failures
                ),
                "cited_claims": len(claims),
            },
        )


def default_cited_synthesizer(
) -> OllamaCitedSynthesizer:
    model = os.getenv(
        "OLLAMA_MODEL",
        "gemma3:4b",
    ).strip()

    return OllamaCitedSynthesizer(
        model=model or "gemma3:4b"
    )
