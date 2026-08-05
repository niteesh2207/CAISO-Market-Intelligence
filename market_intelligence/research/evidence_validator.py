from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.request import Request, urlopen

from market_intelligence.research.evidence_collector import (
    EvidenceDocument,
    EvidencePacket,
)


class EvidenceValidationError(RuntimeError):
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


VALIDATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "relevant": {
            "type": "boolean",
        },
        "relevance_score": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "answerable_from_source": {
            "type": "boolean",
        },
        "source_scope": {
            "type": "string",
            "enum": [
                "direct",
                "partial",
                "background",
                "irrelevant",
            ],
        },
        "supported_claims": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "missing_information": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "reason": {
            "type": "string",
        },
    },
    "required": [
        "relevant",
        "relevance_score",
        "answerable_from_source",
        "source_scope",
        "supported_claims",
        "missing_information",
        "reason",
    ],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """
You are a strict evidence-quality reviewer for an energy-market
research system.

Evaluate whether the supplied source text genuinely helps answer the
specific user question.

Do not treat generic keyword overlap as sufficient.

A source is directly relevant only when it contains factual evidence
about the requested entity, geography, asset, market, regulation,
date, condition or comparison.

Examples:

Question:
Where are data centers in the SDG&E region?

Relevant evidence:
A utility filing, planning document, permit, company announcement or
official map identifying a data-center facility or proposed large
load in SDG&E territory.

Not relevant:
A generic EIA page about U.S. energy statistics, a login portal,
a general data-center article without San Diego or SDG&E evidence,
or a page that merely contains the word region.

Return only the requested JSON structure.
""".strip()


@dataclass(frozen=True)
class ValidatedEvidenceDocument:
    document: EvidenceDocument
    semantic_relevance_score: float
    answerable_from_source: bool
    source_scope: str
    supported_claims: tuple[str, ...]
    missing_information: tuple[str, ...]
    validation_reason: str


@dataclass(frozen=True)
class EvidenceValidationFailure:
    title: str
    url: str
    error: str


@dataclass(frozen=True)
class ValidatedEvidencePacket:
    question: str
    documents: tuple[
        ValidatedEvidenceDocument,
        ...
    ]
    rejected_documents: tuple[
        ValidatedEvidenceDocument,
        ...
    ]
    validation_failures: tuple[
        EvidenceValidationFailure,
        ...
    ] = ()
    sufficient: bool = False
    sufficiency_reason: str = ""


@dataclass(frozen=True)
class OllamaEvidenceValidator:
    model: str = "gemma3:4b"
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 180.0
    minimum_relevance_score: float = 0.62
    http_post: HttpPost = default_http_post

    def _request_validation(
        self,
        *,
        question: str,
        document: EvidenceDocument,
        maximum_text_characters: int,
        compact: bool,
    ) -> dict[str, Any]:
        source_text = document.text[
            :maximum_text_characters
        ]

        if compact:
            user_content = (
                f"Question: {question}\n"
                f"Title: {document.title}\n"
                f"URL: {document.url}\n"
                "Evaluate only whether this source "
                "contains specific factual evidence "
                "that helps answer the question.\n"
                f"Source:\n{source_text}"
            )
        else:
            user_content = (
                f"QUESTION:\n{question}\n\n"
                f"SOURCE TITLE:\n"
                f"{document.title}\n\n"
                f"SOURCE URL:\n"
                f"{document.url}\n\n"
                f"SOURCE TEXT:\n"
                f"{source_text}"
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
                    "content": user_content,
                },
            ],
            "format": VALIDATION_SCHEMA,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 900,
                "top_k": 20,
                "top_p": 0.8,
            },
        }

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
            raise EvidenceValidationError(
                "Ollama returned an empty "
                "validation response."
            )

        try:
            return json.loads(content)

        except json.JSONDecodeError as exc:
            preview = content[:500].replace(
                "\n",
                " ",
            )

            raise EvidenceValidationError(
                "Ollama returned malformed "
                f"validation JSON: {exc}. "
                f"Response preview: {preview!r}"
            ) from exc

    def validate_document(
        self,
        *,
        question: str,
        document: EvidenceDocument,
    ) -> ValidatedEvidenceDocument:
        attempts = (
            (10_000, False),
            (6_000, True),
            (3_500, True),
        )

        errors: list[str] = []

        result: dict[str, Any] | None = None

        for (
            maximum_text_characters,
            compact,
        ) in attempts:
            try:
                result = self._request_validation(
                    question=question,
                    document=document,
                    maximum_text_characters=(
                        maximum_text_characters
                    ),
                    compact=compact,
                )
                break

            except Exception as exc:
                errors.append(
                    f"{type(exc).__name__}: {exc}"
                )

        if result is None:
            raise EvidenceValidationError(
                "Evidence validation failed after "
                f"{len(attempts)} attempts. "
                + " | ".join(errors)
            )

        try:
            score = max(
                0.0,
                min(
                    1.0,
                    float(
                        result[
                            "relevance_score"
                        ]
                    ),
                ),
            )

            source_scope = str(
                result["source_scope"]
            ).strip().lower()

            if source_scope not in {
                "direct",
                "partial",
                "background",
                "irrelevant",
            }:
                source_scope = "irrelevant"

            model_relevant = bool(
                result["relevant"]
            )

            relevant = (
                model_relevant
                and score
                >= self.minimum_relevance_score
                and source_scope
                in {
                    "direct",
                    "partial",
                }
            )

            return ValidatedEvidenceDocument(
                document=document,
                semantic_relevance_score=score,
                answerable_from_source=(
                    bool(
                        result[
                            "answerable_from_source"
                        ]
                    )
                    if relevant
                    else False
                ),
                source_scope=source_scope,
                supported_claims=tuple(
                    str(item).strip()
                    for item in result.get(
                        "supported_claims",
                        (),
                    )
                    if str(item).strip()
                ),
                missing_information=tuple(
                    str(item).strip()
                    for item in result.get(
                        "missing_information",
                        (),
                    )
                    if str(item).strip()
                ),
                validation_reason=str(
                    result.get(
                        "reason",
                        "",
                    )
                ).strip(),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise EvidenceValidationError(
                "Ollama returned a structurally "
                f"invalid validation object: {exc}"
            ) from exc

    def validate_packet(
        self,
        packet: EvidencePacket,
    ) -> ValidatedEvidencePacket:
        accepted = []
        rejected = []
        failures = []

        for document in packet.documents:
            try:
                validation = (
                    self.validate_document(
                        question=packet.question,
                        document=document,
                    )
                )

            except EvidenceValidationError as exc:
                failures.append(
                    EvidenceValidationFailure(
                        title=document.title,
                        url=document.url,
                        error=str(exc),
                    )
                )
                continue

            accepted_document = (
                validation.semantic_relevance_score
                >= self.minimum_relevance_score
                and validation.source_scope
                in {
                    "direct",
                    "partial",
                }
            )

            if accepted_document:
                accepted.append(validation)
            else:
                rejected.append(validation)

        direct_count = sum(
            item.source_scope == "direct"
            for item in accepted
        )

        answerable_count = sum(
            item.answerable_from_source
            for item in accepted
        )

        independent_domains = {
            item.document.url.split(
                "/"
            )[2].lower()
            for item in accepted
            if "://" in item.document.url
        }

        controlling_count = sum(
            item.document.source_tier
            in {
                "controlling",
                "primary",
            }
            for item in accepted
        )

        sufficient = (
            answerable_count >= 1
            and (
                direct_count >= 1
                or controlling_count >= 1
                or len(independent_domains) >= 2
            )
        )

        if sufficient:
            reason = (
                "The packet contains semantically "
                "relevant evidence capable of "
                "supporting an answer."
            )
        elif not accepted:
            reason = (
                "All retrieved pages failed the "
                "semantic relevance gate."
            )
        else:
            reason = (
                "Some pages were relevant, but the "
                "packet does not yet contain enough "
                "direct, answerable evidence."
            )

        return ValidatedEvidencePacket(
            question=packet.question,
            documents=tuple(accepted),
            rejected_documents=tuple(
                rejected
            ),
            validation_failures=tuple(
                failures
            ),
            sufficient=sufficient,
            sufficiency_reason=reason,
        )


def default_evidence_validator(
) -> OllamaEvidenceValidator:
    model = os.getenv(
        "OLLAMA_MODEL",
        "gemma3:4b",
    ).strip()

    return OllamaEvidenceValidator(
        model=model or "gemma3:4b"
    )
