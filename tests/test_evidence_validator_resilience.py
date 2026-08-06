import json

from market_intelligence.research.evidence_collector import (
    EvidenceDocument,
    EvidencePacket,
)
from market_intelligence.research.evidence_validator import (
    OllamaEvidenceValidator,
)


def sample_document(
    title="SDG&E planning filing",
    url="https://sdge.com/planning",
):
    return EvidenceDocument(
        title=title,
        url=url,
        provider="SDG&E",
        text=(
            "The SDG&E filing discusses large "
            "electrical loads and data centers "
            "in the San Diego service area. "
            * 80
        ),
        retrieved_at=(
            "2026-08-05T12:00:00Z"
        ),
        source_tier="primary",
        official=True,
        discovery_score=25.0,
        relevance_score=15.0,
        matched_terms=(
            "centers",
            "sdg&e",
            "san",
            "diego",
        ),
    )


def valid_envelope():
    result = {
        "relevant": True,
        "relevance_score": 0.91,
        "answerable_from_source": True,
        "source_scope": "direct",
        "supported_claims": [
            "The filing discusses data centers."
        ],
        "missing_information": [],
        "reason": (
            "The source directly addresses "
            "the requested topic."
        ),
    }

    return json.dumps(
        {
            "message": {
                "content": json.dumps(result)
            }
        }
    ).encode("utf-8")


def test_validator_retries_after_malformed_json():
    calls = {"count": 0}

    def fake_post(*_args):
        calls["count"] += 1

        if calls["count"] == 1:
            return json.dumps(
                {
                    "message": {
                        "content": (
                            '{"relevant": true, '
                            '"reason": "unterminated'
                        )
                    }
                }
            ).encode("utf-8")

        return valid_envelope()

    validator = OllamaEvidenceValidator(
        http_post=fake_post
    )

    result = validator.validate_document(
        question=(
            "Where are data centers "
            "in SDG&E territory?"
        ),
        document=sample_document(),
    )

    assert calls["count"] == 2
    assert result.source_scope == "direct"
    assert (
        result.semantic_relevance_score
        == 0.91
    )


def test_one_failed_document_does_not_abort_packet():
    calls = {"count": 0}

    def fake_post(*_args):
        calls["count"] += 1

        if calls["count"] <= 3:
            return json.dumps(
                {
                    "message": {
                        "content": (
                            '{"relevant": false, '
                            '"reason": "broken'
                        )
                    }
                }
            ).encode("utf-8")

        return valid_envelope()

    validator = OllamaEvidenceValidator(
        http_post=fake_post
    )

    packet = EvidencePacket(
        question=(
            "Where are data centers "
            "in SDG&E territory?"
        ),
        documents=(
            sample_document(
                title="Broken source",
                url="https://example.com/broken",
            ),
            sample_document(),
        ),
        failures=(),
        controlling_source_count=1,
        independent_domain_count=2,
        sufficient=True,
        sufficiency_reason="Test packet.",
    )

    result = validator.validate_packet(
        packet
    )

    assert len(
        result.validation_failures
    ) == 1

    assert len(result.documents) == 1
    assert result.sufficient is True
