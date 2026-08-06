from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from urllib.parse import urlsplit, urlunsplit

from market_intelligence.research.evidence_validator import (
    ValidatedEvidenceDocument,
    ValidatedEvidencePacket,
)


IGNORED_QUERY_KEYS = {
    "sid",
    "os",
    "ref",
    "source",
    "campaign",
    "fbclid",
    "gclid",
}


GENERIC_PAGE_TITLES = {
    "homepage",
    "home",
    "welcome",
    "what's new",
}


def normalized_url(
    url: str,
) -> str:
    parsed = urlsplit(url)

    hostname = (
        parsed.hostname
        or ""
    ).lower().removeprefix("www.")

    port = parsed.port

    if (
        port is None
        or (
            parsed.scheme == "https"
            and port == 443
        )
        or (
            parsed.scheme == "http"
            and port == 80
        )
    ):
        netloc = hostname
    else:
        netloc = f"{hostname}:{port}"

    path = re.sub(
        r"/+",
        "/",
        parsed.path or "/",
    )

    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            path,
            "",
            "",
        )
    )


def normalized_text(
    text: str,
) -> str:
    cleaned = re.sub(
        r"\s+",
        " ",
        text.lower(),
    ).strip()

    return cleaned[:12_000]


def content_fingerprint(
    document: ValidatedEvidenceDocument,
) -> str:
    value = normalized_text(
        document.document.text
    )

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def is_generic_homepage(
    document: ValidatedEvidenceDocument,
) -> bool:
    title = (
        document.document.title
        .strip()
        .lower()
    )

    path = urlsplit(
        document.document.url
    ).path.strip("/")

    return (
        title in GENERIC_PAGE_TITLES
        or (
            not path
            and document.source_scope
            != "direct"
        )
    )


def deduplicate_validated_packet(
    packet: ValidatedEvidencePacket,
) -> ValidatedEvidencePacket:
    retained: list[
        ValidatedEvidenceDocument
    ] = []

    rejected = list(
        packet.rejected_documents
    )

    seen_urls: set[str] = set()
    seen_fingerprints: set[str] = set()

    for item in packet.documents:
        canonical_url = normalized_url(
            item.document.url
        )

        fingerprint = content_fingerprint(
            item
        )

        duplicate = (
            canonical_url in seen_urls
            or fingerprint
            in seen_fingerprints
        )

        if duplicate or is_generic_homepage(
            item
        ):
            rejected.append(item)
            continue

        seen_urls.add(canonical_url)
        seen_fingerprints.add(
            fingerprint
        )
        retained.append(item)

    sufficient = bool(retained)

    return replace(
        packet,
        documents=tuple(retained),
        rejected_documents=tuple(
            rejected
        ),
        sufficient=sufficient,
        sufficiency_reason=(
            "Unique, non-generic evidence "
            "is available."
            if sufficient
            else (
                "All accepted documents were "
                "duplicates or generic pages."
            )
        ),
    )
