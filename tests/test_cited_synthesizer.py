import json

from market_intelligence.research.cited_synthesizer import (
    OllamaCitedSynthesizer,
)
from market_intelligence.research.evidence_collector import (
    EvidenceDocument,
)
from market_intelligence.research.evidence_validator import (
    ValidatedEvidenceDocument,
    ValidatedEvidencePacket,
)


def evidence_document(
    *,
    title="SDG&E Large Load Filing",
    url="https://sdge.com/large-load",
):
    document = EvidenceDocument(
        title=title,
        url=url,
        provider="San Diego Gas & Electric",
        text=(
            "The filing identifies a proposed "
            "large-load data-center project within "
            "SDG&E service territory. "
            * 30
        ),
        retrieved_at=(
            "2026-08-05T12:00:00Z"
        ),
        source_tier="primary",
        official=True,
        discovery_score=30.0,
        relevance_score=20.0,
        matched_terms=(
            "centers",
            "sdg&e",
        ),
    )

    return ValidatedEvidenceDocument(
        document=document,
        semantic_relevance_score=0.95,
        answerable_from_source=True,
        source_scope="direct",
        supported_claims=(
            (
                "The filing identifies a proposed "
                "data-center project in SDG&E "
                "service territory."
            ),
        ),
        missing_information=(
            (
                "The filing does not establish "
                "an exhaustive list of all "
                "data centers."
            ),
        ),
        validation_reason=(
            "The source directly addresses "
            "the facility and geography."
        ),
    )


def sufficient_packet():
    return ValidatedEvidencePacket(
        question=(
            "Where are the data centers "
            "in the SDG&E region?"
        ),
        documents=(
            evidence_document(),
        ),
        rejected_documents=(),
        validation_failures=(),
        sufficient=True,
        sufficiency_reason=(
            "Direct primary evidence exists."
        ),
    )


def test_synthesizer_returns_cited_answer():
    result = {
        "direct_answer": (
            "The available filing identifies "
            "at least one proposed data-center "
            "project in SDG&E territory."
        ),
        "explanation": (
            "The evidence confirms one project, "
            "but does not provide an exhaustive "
            "regional inventory."
        ),
        "confidence": "medium",
        "claims": [
            {
                "text": (
                    "A proposed data-center project "
                    "was identified in SDG&E "
                    "service territory."
                ),
                "source_ids": [1],
                "claim_type": "fact",
            }
        ],
        "limitations": [
            (
                "Public evidence does not establish "
                "a complete inventory."
            )
        ],
    }

    envelope = {
        "message": {
            "content": json.dumps(result)
        }
    }

    synthesizer = OllamaCitedSynthesizer(
        http_post=lambda *_: json.dumps(
            envelope
        ).encode("utf-8")
    )

    answer = synthesizer.synthesize(
        sufficient_packet()
    )

    assert answer.status == "answered"
    assert answer.confidence == "medium"
    assert len(answer.claims) == 1
    assert answer.claims[0].source_ids == (1,)
    assert len(answer.sources) == 1
    assert answer.sources[0].source_id == 1


def test_invalid_source_id_is_removed():
    result = {
        "direct_answer": "Partial answer.",
        "explanation": "Explanation.",
        "confidence": "low",
        "claims": [
            {
                "text": "Unsupported source.",
                "source_ids": [99],
                "claim_type": "fact",
            }
        ],
        "limitations": [],
    }

    envelope = {
        "message": {
            "content": json.dumps(result)
        }
    }

    synthesizer = OllamaCitedSynthesizer(
        http_post=lambda *_: json.dumps(
            envelope
        ).encode("utf-8")
    )

    answer = synthesizer.synthesize(
        sufficient_packet()
    )

    assert not answer.claims


def test_insufficient_packet_returns_held():
    packet = ValidatedEvidencePacket(
        question="Unanswerable question",
        documents=(),
        rejected_documents=(),
        validation_failures=(),
        sufficient=False,
        sufficiency_reason=(
            "No validated direct evidence."
        ),
    )

    answer = OllamaCitedSynthesizer(
        http_post=lambda *_: b""
    ).synthesize(packet)

    assert answer.status == "held"
    assert answer.confidence == "insufficient"
    assert not answer.sources
