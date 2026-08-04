import json
from io import BytesIO
from zipfile import ZipFile

import pytest

from market_intelligence.connectors.eia_bulk import (
    EiaBulkClient,
    EiaBulkHttpResponse,
    parse_eia_bulk_manifest,
)
from market_intelligence.retrieval.exceptions import (
    SourceResponseError,
    SourceUnauthorizedError,
)


MANIFEST_PAYLOAD = {
    "files": [
        {
            "identifier": "EBA",
            "data_set": (
                "U.S. Electric System Operating Data "
                "(2019-present)"
            ),
            "title": (
                "Hourly demand, generation and interchange"
            ),
            "last_updated": "2026-08-03",
            "modified": "2026-08-03T15:30:00Z",
            "category_id": "electricity",
            "download_url": (
                "https://api.eia.gov/bulk/EBA.zip"
            ),
        },
        {
            "identifier": "NG",
            "data_set": "Natural Gas",
            "title": "Natural gas data",
            "last_updated": "2026-08-03",
            "download_url": (
                "https://api.eia.gov/bulk/NG.zip"
            ),
        },
    ]
}


def response(
    url,
    body,
    *,
    status=200,
    final_url=None,
):
    return EiaBulkHttpResponse(
        requested_url=url,
        final_url=final_url or url,
        status_code=status,
        content_type="application/json",
        body=body,
        headers={},
    )


def zip_bytes():
    buffer = BytesIO()

    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "EBA.json",
            '{"series":[]}',
        )

    return buffer.getvalue()


def test_manifest_parses_files():
    manifest = parse_eia_bulk_manifest(
        MANIFEST_PAYLOAD
    )

    assert len(manifest.files) == 2
    assert manifest.files[0].identifier == "EBA"
    assert manifest.files[0].last_updated == (
        "2026-08-03"
    )


def test_manifest_rejects_external_url():
    payload = {
        "files": [
            {
                "identifier": "BAD",
                "data_set": "Bad",
                "title": "Bad file",
                "download_url": (
                    "https://untrusted.example/file.zip"
                ),
            }
        ]
    }

    with pytest.raises(
        SourceUnauthorizedError,
        match="unapproved",
    ):
        parse_eia_bulk_manifest(payload)


def test_search_finds_operating_data():
    client = EiaBulkClient()
    manifest = parse_eia_bulk_manifest(
        MANIFEST_PAYLOAD
    )

    matches = client.search(
        manifest,
        "electric system",
        "operating data",
    )

    assert len(matches) == 1
    assert matches[0].identifier == "EBA"


def test_live_manifest_response_is_parsed():
    client = EiaBulkClient(
        http_get=lambda url, headers, timeout, maximum: (
            response(
                url,
                json.dumps(
                    MANIFEST_PAYLOAD
                ).encode("utf-8"),
            )
        )
    )

    manifest = client.manifest()

    assert len(manifest.files) == 2


def test_invalid_manifest_json_is_rejected():
    client = EiaBulkClient(
        http_get=lambda url, headers, timeout, maximum: (
            response(url, b"not-json")
        )
    )

    with pytest.raises(
        SourceResponseError,
        match="valid JSON",
    ):
        client.manifest()


def test_download_validates_zip():
    client = EiaBulkClient(
        http_get=lambda url, headers, timeout, maximum: (
            response(
                url,
                zip_bytes(),
            )
        )
    )

    file = parse_eia_bulk_manifest(
        MANIFEST_PAYLOAD
    ).files[0]

    archive = client.download(file)

    assert archive.member_names == (
        "EBA.json",
    )


def test_invalid_zip_is_rejected():
    client = EiaBulkClient(
        http_get=lambda url, headers, timeout, maximum: (
            response(url, b"not-a-zip")
        )
    )

    file = parse_eia_bulk_manifest(
        MANIFEST_PAYLOAD
    ).files[0]

    with pytest.raises(
        SourceResponseError,
        match="valid ZIP",
    ):
        client.download(file)


def test_external_redirect_is_rejected():
    client = EiaBulkClient(
        http_get=lambda url, headers, timeout, maximum: (
            response(
                url,
                zip_bytes(),
                final_url=(
                    "https://untrusted.example/file.zip"
                ),
            )
        )
    )

    file = parse_eia_bulk_manifest(
        MANIFEST_PAYLOAD
    ).files[0]

    with pytest.raises(
        SourceUnauthorizedError,
        match="redirected outside",
    ):
        client.download(file)


def test_nested_manifest_dictionary_is_parsed():
    payload = {
        "manifest": {
            "EBA": {
                "data_set": "EBA",
                "title": (
                    "U.S. Electric System Operating Data "
                    "(2019-present)"
                ),
                "last_updated": "2026-08-03",
                "accessURL": (
                    "http://api.eia.gov/bulk/EBA.zip"
                ),
            },
            "NG": {
                "data_set": "NG",
                "title": "Natural Gas",
                "last_updated": "2026-08-03",
                "accessURL": (
                    "https://api.eia.gov/bulk/NG.zip"
                ),
            },
        }
    }

    manifest = parse_eia_bulk_manifest(payload)

    assert len(manifest.files) == 2
    assert manifest.files[0].identifier == "EBA"
    assert manifest.files[0].download_url == (
        "https://api.eia.gov/bulk/EBA.zip"
    )


def test_dataset_list_envelope_is_parsed():
    payload = {
        "dataset": [
            {
                "identifier": "EBA",
                "data_set": "EBA",
                "title": (
                    "U.S. Electric System Operating Data"
                ),
                "accessURL": (
                    "https://api.eia.gov/bulk/EBA.zip"
                ),
            }
        ]
    }

    manifest = parse_eia_bulk_manifest(payload)

    assert len(manifest.files) == 1
    assert manifest.files[0].identifier == "EBA"


def test_access_url_field_is_supported():
    payload = [
        {
            "identifier": "NG",
            "data_set": "Natural Gas",
            "title": "Natural Gas",
            "accessURL": (
                "https://api.eia.gov/bulk/NG.zip"
            ),
        }
    ]

    manifest = parse_eia_bulk_manifest(payload)

    assert manifest.files[0].download_url.endswith(
        "/NG.zip"
    )


def test_identifier_key_is_preserved_from_map():
    payload = {
        "results": {
            "PET": {
                "data_set": "Petroleum",
                "title": "Petroleum",
                "accessURL": (
                    "https://api.eia.gov/bulk/PET.zip"
                ),
            }
        }
    }

    manifest = parse_eia_bulk_manifest(payload)

    assert manifest.files[0].identifier == "PET"


def test_download_uses_browser_compatible_accept_header():
    captured = {}

    def fake_get(
        url,
        headers,
        timeout,
        maximum,
    ):
        captured["headers"] = dict(headers)

        return response(
            url,
            zip_bytes(),
        )

    client = EiaBulkClient(
        http_get=fake_get
    )

    file = parse_eia_bulk_manifest(
        MANIFEST_PAYLOAD
    ).files[0]

    client.download(file)

    assert captured["headers"]["Accept"] == "*/*"
    assert (
        captured["headers"]["Accept-Encoding"]
        == "identity"
    )
    assert "Mozilla/5.0" in (
        captured["headers"]["User-Agent"]
    )

