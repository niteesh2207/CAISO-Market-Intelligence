import json

from market_intelligence.research.evidence_collector import (
    EvidenceDocument,
    EvidencePacket,
)
from market_intelligence.research.evidence_validator import (
    OllamaEvidenceValidator,
)


def document(
    *,
    title,
    url,
    text,
    tier="supporting",
):
    return EvidenceDocument(
        title=title,
        url=url,
        provider="test",
        text=text,
        retrieved_at=(
            "2026-08-05T12:00:00Z"
        ),
        source_tier=tier,
        official=(
            tier in {
                "controlling",
                "primary",
            }
        ),
        discovery_score=20.0,
        relevance_score=10.0,
        matched_terms=(),
    )


def fake_response(payload):
    envelope = {
        "message": {
            "content": json.dumps(payload)
        }
    }

    return json.dumps(
        envelope
    ).encode("utf-8")


def test_direct_utility_evidence_is_accepted():
    payload = {
        "relevant": True,
        "relevance_score": 0.94,
        "answerable_from_source": True,
        "source_scope": "direct",
        "supported_claims": [
            (
                "The filing identifies a "
                "data-center project in SDG&E "
                "service territory."
            )
        ],
        "missing_information": [],
        "reason": (
            "The source directly identifies "
            "the requested facility and geography."
        ),
    }

    validator = OllamaEvidenceValidator(
        http_post=lambda *_: (
            fake_response(payload)
        )
    )

    packet = EvidencePacket(
        question=(
            "Where are the data centers "
            "in the SDG&E region?"
        ),
        documents=(
            document(
                title=(
                    "SDG&E Large Load Filing"
                ),
                url=(
                    "https://sdge.com/"
                    "large-load-filing"
                ),
                text=(
                    "The filing identifies a "
                    "data center in SDG&E territory."
                ),
                tier="primary",
            ),
        ),
        failures=(),
        controlling_source_count=1,
        independent_domain_count=1,
        sufficient=True,
        sufficiency_reason="Primary source.",
    )

    result = validator.validate_packet(
        packet
    )

    assert result.sufficient is True
    assert len(result.documents) == 1
    assert not result.rejected_documents


def test_generic_eia_page_is_rejected():
    payload = {
        "relevant": False,
        "relevance_score": 0.13,
        "answerable_from_source": False,
        "source_scope": "irrelevant",
        "supported_claims": [],
        "missing_information": [
            "No SDG&E data-center locations",
            "No San Diego facility information",
        ],
        "reason": (
            "The page contains generic national "
            "energy information only."
        ),
    }

    validator = OllamaEvidenceValidator(
        http_post=lambda *_: (
            fake_response(payload)
        )
    )

    packet = EvidencePacket(
        question=(
            "Where are the data centers "
            "in the SDG&E region?"
        ),
        documents=(
            document(
                title="EIA What's New",
                url=(
                    "https://www.eia.gov/"
                    "about/new/"
                ),
                text=(
                    "General information about "
                    "national energy statistics."
                ),
                tier="controlling",
            ),
        ),
        failures=(),
        controlling_source_count=1,
        independent_domain_count=1,
        sufficient=True,
        sufficiency_reason=(
            "Controlling source."
        ),
    )

    result = validator.validate_packet(
        packet
    )

    assert result.sufficient is False
    assert not result.documents
    assert (
        len(result.rejected_documents)
        == 1
    )
