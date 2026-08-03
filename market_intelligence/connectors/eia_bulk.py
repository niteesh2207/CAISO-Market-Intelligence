from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile


from market_intelligence.retrieval.exceptions import (
    SourceRateLimitedError,
    SourceResponseError,
    SourceUnauthorizedError,
    SourceUnavailableError,
)


EIA_BULK_MANIFEST_URL = (
    "https://api.eia.gov/bulk/manifest.txt"
)

MAX_MANIFEST_BYTES = 5_000_000
MAX_BULK_ARCHIVE_BYTES = 2_000_000_000
MAX_ARCHIVE_MEMBERS = 100_000


@dataclass(frozen=True)
class EiaBulkHttpResponse:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    headers: dict[str, str]


EiaBulkHttpGet = Callable[
    [str, dict[str, str], int, int],
    EiaBulkHttpResponse,
]


@dataclass(frozen=True)
class EiaBulkFile:
    identifier: str
    data_set: str
    title: str
    last_updated: str | None
    modified: str | None
    category_id: str | None
    download_url: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class EiaBulkManifest:
    retrieved_at: datetime
    source_url: str
    files: tuple[EiaBulkFile, ...]


@dataclass(frozen=True)
class EiaBulkArchive:
    file: EiaBulkFile
    final_url: str
    retrieved_at: datetime
    body: bytes
    member_names: tuple[str, ...]


def _approved_eia_bulk_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    return (
        parsed.scheme.lower() == "https"
        and (
            hostname == "api.eia.gov"
            or hostname.endswith(".eia.gov")
        )
    )


def _default_http_get(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
    maximum_bytes: int,
) -> EiaBulkHttpResponse:
    request = Request(
        url,
        headers=headers,
        method="GET",
    )

    try:
        with urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            body = response.read(
                maximum_bytes + 1
            )

            return EiaBulkHttpResponse(
                requested_url=url,
                final_url=response.geturl(),
                status_code=int(response.getcode()),
                content_type=response.headers.get(
                    "Content-Type",
                    "",
                ),
                body=body,
                headers={
                    key.lower(): value
                    for key, value
                    in response.headers.items()
                },
            )

    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise SourceUnauthorizedError(
                f"EIA bulk service returned HTTP {exc.code}."
            ) from exc

        if exc.code == 429:
            raise SourceRateLimitedError(
                "EIA bulk service rate limit reached."
            ) from exc

        if exc.code >= 500:
            raise SourceUnavailableError(
                f"EIA bulk service returned HTTP {exc.code}."
            ) from exc

        raise SourceResponseError(
            f"EIA bulk service returned HTTP {exc.code}."
        ) from exc

    except URLError as exc:
        raise SourceUnavailableError(
            f"EIA bulk network failure: {exc.reason}"
        ) from exc


def _validate_response(
    response: EiaBulkHttpResponse,
    *,
    maximum_bytes: int,
) -> None:
    if response.status_code in {401, 403}:
        raise SourceUnauthorizedError(
            f"EIA bulk service returned HTTP "
            f"{response.status_code}."
        )

    if response.status_code == 429:
        raise SourceRateLimitedError(
            "EIA bulk service rate limit reached."
        )

    if response.status_code >= 500:
        raise SourceUnavailableError(
            f"EIA bulk service returned HTTP "
            f"{response.status_code}."
        )

    if not 200 <= response.status_code < 300:
        raise SourceResponseError(
            f"Unexpected EIA bulk HTTP status "
            f"{response.status_code}."
        )

    if not _approved_eia_bulk_url(
        response.final_url
    ):
        raise SourceUnauthorizedError(
            "EIA bulk response redirected outside "
            "approved EIA HTTPS domains."
        )

    if not response.body:
        raise SourceResponseError(
            "EIA bulk service returned an empty response."
        )

    if len(response.body) > maximum_bytes:
        raise SourceResponseError(
            "EIA bulk response exceeded the configured "
            "size limit."
        )


def _looks_like_manifest_record(
    value: dict[str, Any],
) -> bool:
    """
    Distinguish an actual bulk-file record from a
    container such as {"dataset": [...]}.

    Container keys whose values are lists or dictionaries
    do not count as record fields.
    """

    scalar_values = {
        str(key).strip().lower(): item
        for key, item in value.items()
        if not isinstance(item, (dict, list))
        and item is not None
        and str(item).strip()
    }

    keys = set(scalar_values)

    identifier_keys = {
        "identifier",
        "id",
    }

    dataset_keys = {
        "data_set",
        "dataset",
        "datasetid",
        "name",
    }

    title_keys = {
        "title",
        "description",
    }

    url_keys = {
        "accessurl",
        "access_url",
        "downloadurl",
        "download_url",
        "file_url",
        "url",
        "link",
    }

    has_identifier = bool(keys & identifier_keys)
    has_dataset = bool(keys & dataset_keys)
    has_title = bool(keys & title_keys)
    has_url = bool(keys & url_keys)

    # A usable file record normally exposes either:
    # 1. an identifier plus descriptive information, or
    # 2. a dataset/title plus a direct file URL.
    return (
        has_identifier
        and (
            has_dataset
            or has_title
            or has_url
        )
    ) or (
        has_url
        and (
            has_dataset
            or has_title
        )
    )


def _records_from_manifest_payload(
    payload: Any,
) -> list[dict[str, Any]]:
    """
    Recursively locate EIA bulk dataset records.

    The public manifest has appeared in more than one
    JSON envelope over time, including lists, named
    containers and identifier-keyed dictionaries.
    """

    records: list[dict[str, Any]] = []
    visited: set[int] = set()

    container_names = {
        "files",
        "file",
        "data",
        "manifest",
        "manifests",
        "dataset",
        "datasets",
        "bulk",
        "bulk_files",
        "bulkfiles",
        "response",
        "results",
        "items",
    }

    def walk(
        value: Any,
        *,
        inherited_identifier: str | None = None,
    ) -> None:
        if isinstance(value, (dict, list)):
            object_id = id(value)

            if object_id in visited:
                return

            visited.add(object_id)

        if isinstance(value, list):
            for item in value:
                walk(item)

            return

        if not isinstance(value, dict):
            return

        if _looks_like_manifest_record(value):
            record = dict(value)

            if (
                inherited_identifier
                and not any(
                    record.get(name)
                    for name in (
                        "identifier",
                        "id",
                    )
                )
            ):
                record["identifier"] = (
                    inherited_identifier
                )

            records.append(record)
            return

        for key, child in value.items():
            normalized_key = (
                str(key)
                .strip()
                .lower()
                .replace("-", "_")
                .replace(" ", "_")
            )

            if isinstance(child, dict):
                child_identifier = (
                    None
                    if normalized_key in container_names
                    else str(key).strip()
                )

                walk(
                    child,
                    inherited_identifier=(
                        child_identifier
                        or inherited_identifier
                    ),
                )

            elif isinstance(child, list):
                walk(child)

    walk(payload)

    # Remove duplicate records without relying on every
    # manifest version exposing exactly the same fields.
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for record in records:
        identifier = str(
            record.get("identifier")
            or record.get("id")
            or ""
        ).strip()

        data_set = str(
            record.get("data_set")
            or record.get("dataset")
            or record.get("name")
            or ""
        ).strip()

        access_url = str(
            record.get("accessURL")
            or record.get("accessUrl")
            or record.get("access_url")
            or record.get("downloadURL")
            or record.get("download_url")
            or record.get("url")
            or ""
        ).strip()

        signature = (
            identifier,
            data_set,
            access_url,
        )

        if signature in seen:
            continue

        seen.add(signature)
        unique.append(record)

    if not unique:
        raise SourceResponseError(
            "EIA bulk manifest has an unsupported "
            "or empty JSON structure."
        )

    return unique


def _first_text(
    record: dict[str, Any],
    *names: str,
) -> str | None:
    for name in names:
        value = record.get(name)

        if value is not None:
            cleaned = str(value).strip()

            if cleaned:
                return cleaned

    return None


def _resolve_download_url(
    record: dict[str, Any],
    identifier: str,
) -> str:
    explicit = _first_text(
        record,
        "accessURL",
        "accessUrl",
        "access_url",
        "downloadURL",
        "downloadUrl",
        "download_url",
        "url",
        "file_url",
        "link",
    )

    if explicit:
        if explicit.startswith("http://"):
            explicit = (
                "https://"
                + explicit[len("http://"):]
            )

        return explicit

    file_name = _first_text(
        record,
        "file_name",
        "filename",
        "file",
    )

    if file_name:
        return (
            "https://api.eia.gov/bulk/"
            f"{file_name.lstrip('/')}"
        )

    if identifier.lower().endswith(".zip"):
        return (
            "https://api.eia.gov/bulk/"
            f"{identifier}"
        )

    return (
        "https://api.eia.gov/bulk/"
        f"{identifier}.zip"
    )


def parse_eia_bulk_manifest(
    payload: Any,
    *,
    source_url: str = EIA_BULK_MANIFEST_URL,
    retrieved_at: datetime | None = None,
) -> EiaBulkManifest:
    records = _records_from_manifest_payload(
        payload
    )

    files: list[EiaBulkFile] = []

    for record in records:
        identifier = _first_text(
            record,
            "identifier",
            "id",
            "data_set",
            "dataset",
            "name",
        )

        data_set = _first_text(
            record,
            "data_set",
            "dataset",
            "dataSet",
            "name",
            "description",
        )

        title = _first_text(
            record,
            "title",
            "name",
            "description",
        )

        if not identifier or not data_set or not title:
            continue

        download_url = _resolve_download_url(
            record,
            identifier,
        )

        if not _approved_eia_bulk_url(
            download_url
        ):
            raise SourceUnauthorizedError(
                "EIA bulk manifest contained an "
                "unapproved download URL."
            )

        files.append(
            EiaBulkFile(
                identifier=identifier,
                data_set=data_set,
                title=title,
                last_updated=_first_text(
                    record,
                    "last_updated",
                    "lastUpdated",
                ),
                modified=_first_text(
                    record,
                    "modified",
                ),
                category_id=_first_text(
                    record,
                    "category_id",
                    "categoryId",
                ),
                download_url=download_url,
                raw=dict(record),
            )
        )

    if not files:
        raise SourceResponseError(
            "EIA bulk manifest contained no usable files."
        )

    return EiaBulkManifest(
        retrieved_at=(
            retrieved_at
            or datetime.now(timezone.utc)
        ),
        source_url=source_url,
        files=tuple(files),
    )


class EiaBulkClient:
    def __init__(
        self,
        *,
        http_get: EiaBulkHttpGet | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        self.http_get = (
            http_get
            or _default_http_get
        )
        self.timeout_seconds = timeout_seconds

    def manifest(self) -> EiaBulkManifest:
        response = self.http_get(
            EIA_BULK_MANIFEST_URL,
            {
                "Accept": "application/json,text/plain",
                "User-Agent": (
                    "CAISO-Market-Intelligence/0.1 "
                    "(official EIA bulk-data retrieval)"
                ),
            },
            self.timeout_seconds,
            MAX_MANIFEST_BYTES,
        )

        _validate_response(
            response,
            maximum_bytes=MAX_MANIFEST_BYTES,
        )

        try:
            payload = json.loads(
                response.body.decode("utf-8-sig")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise SourceResponseError(
                "EIA bulk manifest was not valid JSON."
            ) from exc

        return parse_eia_bulk_manifest(
            payload,
            source_url=response.final_url,
        )

    def search(
        self,
        manifest: EiaBulkManifest,
        *terms: str,
    ) -> tuple[EiaBulkFile, ...]:
        normalized_terms = tuple(
            re.sub(
                r"[^a-z0-9]+",
                " ",
                term.lower(),
            ).strip()
            for term in terms
            if term.strip()
        )

        matches = []

        for file in manifest.files:
            haystack = re.sub(
                r"[^a-z0-9]+",
                " ",
                " ".join(
                    [
                        file.identifier,
                        file.data_set,
                        file.title,
                    ]
                ).lower(),
            )

            if all(
                term in haystack
                for term in normalized_terms
            ):
                matches.append(file)

        return tuple(matches)

    def download(
        self,
        file: EiaBulkFile,
    ) -> EiaBulkArchive:
        if not _approved_eia_bulk_url(
            file.download_url
        ):
            raise SourceUnauthorizedError(
                "EIA bulk file URL is outside "
                "approved EIA HTTPS domains."
            )

        response = self.http_get(
            file.download_url,
            {
                # Some EIA www-hosted bulk archives return
                # HTTP 406 when the client advertises only
                # ZIP-specific media types. Accept any official
                # response and validate the ZIP bytes ourselves.
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/148.0 Safari/537.36 "
                    "CAISO-Market-Intelligence/0.1"
                ),
            },
            self.timeout_seconds,
            MAX_BULK_ARCHIVE_BYTES,
        )

        _validate_response(
            response,
            maximum_bytes=MAX_BULK_ARCHIVE_BYTES,
        )

        try:
            archive = ZipFile(
                BytesIO(response.body)
            )
        except BadZipFile as exc:
            raise SourceResponseError(
                "EIA bulk file was not a valid ZIP archive."
            ) from exc

        members = [
            info
            for info in archive.infolist()
            if not info.is_dir()
        ]

        if not members:
            raise SourceResponseError(
                "EIA bulk ZIP contained no files."
            )

        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise SourceResponseError(
                "EIA bulk ZIP contained too many members."
            )

        for member in members:
            parts = (
                member.filename
                .replace("\\", "/")
                .split("/")
            )

            if (
                member.filename.startswith(("/", "\\"))
                or ".." in parts
            ):
                raise SourceResponseError(
                    "EIA bulk ZIP contained an unsafe path."
                )

        return EiaBulkArchive(
            file=file,
            final_url=response.final_url,
            retrieved_at=datetime.now(
                timezone.utc
            ),
            body=response.body,
            member_names=tuple(
                member.filename
                for member in members
            ),
        )
