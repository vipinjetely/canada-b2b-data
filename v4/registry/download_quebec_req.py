from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = ROOT / "data" / "raw" / "v4" / "quebec_req"
ZIP_PATH = RAW_DIR / "quebec_req_registry.zip"
METADATA_PATH = RAW_DIR / "quebec_req_download_metadata.json"

# Official REQ bulk-download endpoint published by Données Québec.
DOWNLOAD_URL = (
    "https://www.registreentreprises.gouv.qc.ca/"
    "RQAnonymeGR/GR/GR03/"
    "GR03A2_22A_PIU_RecupDonnPub_PC/"
    "FichierDonneesOuvertes.aspx"
)

DATASET_PAGE = (
    "https://www.donneesquebec.ca/recherche/dataset/"
    "registre-des-entreprises"
)

SOURCE_KEY = "QUEBEC_REQ"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def main() -> None:
    print("=== V4 QUEBEC REQ DOWNLOAD ===")
    print()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    collected_at = datetime.now(
        timezone.utc
    ).isoformat()

    temp_path = ZIP_PATH.with_suffix(".tmp")

    print("Downloading official Quebec REQ dataset...")
    print(f"Source: {DOWNLOAD_URL}")
    print()

    bytes_downloaded = 0

    try:
        with requests.get(
            DOWNLOAD_URL,
            timeout=(20, 600),
            stream=True,
            allow_redirects=True,
            headers={
                "User-Agent":
                    "Canada-B2B-Data-Automation/4.0"
            },
        ) as response:

            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type"
            )

            content_length = response.headers.get(
                "Content-Length"
            )

            last_modified = response.headers.get(
                "Last-Modified"
            )

            etag = response.headers.get("ETag")

            final_url = response.url

            with temp_path.open("wb") as handle:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if not chunk:
                        continue

                    handle.write(chunk)
                    bytes_downloaded += len(chunk)

        if bytes_downloaded == 0:
            raise RuntimeError(
                "Downloaded Quebec REQ file is empty."
            )

        if not zipfile.is_zipfile(temp_path):
            raise RuntimeError(
                "Downloaded file is not a valid ZIP archive. "
                "The official endpoint may have returned an "
                "HTML page or changed its download flow."
            )

        temp_path.replace(ZIP_PATH)

    finally:
        if temp_path.exists():
            temp_path.unlink()

    checksum = sha256_file(ZIP_PATH)

    with zipfile.ZipFile(ZIP_PATH, "r") as archive:
        members = archive.infolist()

        csv_members = [
            item
            for item in members
            if item.filename.lower().endswith(".csv")
        ]

        inventory = [
            {
                "filename": item.filename,
                "uncompressed_bytes": item.file_size,
                "compressed_bytes": item.compress_size,
            }
            for item in members
        ]

    if len(csv_members) != 6:
        raise RuntimeError(
            "Expected exactly 6 CSV files in official "
            f"Quebec REQ archive; found {len(csv_members)}."
        )

    metadata = {
        "source_key": SOURCE_KEY,
        "registry_type": "PROVINCIAL_REGISTRY",
        "jurisdiction": "Quebec",

        "dataset_page": DATASET_PAGE,
        "source_url": DOWNLOAD_URL,
        "final_download_url": final_url,

        "collected_at_utc": collected_at,

        "http_content_type": content_type,
        "http_content_length": content_length,
        "http_last_modified": last_modified,
        "http_etag": etag,

        "downloaded_bytes": bytes_downloaded,
        "sha256": checksum,

        "archive_path": str(ZIP_PATH),

        "csv_file_count": len(csv_members),
        "archive_member_count": len(members),

        "archive_inventory": inventory,

        "join_key": "NEQ",

        "licence": "CC-BY-NC-SA 4.0",

        "provenance_status":
            "OFFICIAL_QUEBEC_REQ_BULK_DATA",
    }

    METADATA_PATH.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("Download completed successfully.")
    print()
    print(f"Downloaded bytes : {bytes_downloaded:,}")
    print(f"CSV files        : {len(csv_members)}")
    print(f"Archive members  : {len(members)}")
    print(f"SHA-256          : {checksum}")
    print()

    print("CSV inventory:")

    for item in csv_members:
        print(
            f"  - {item.filename} "
            f"({item.file_size:,} bytes)"
        )

    print()
    print(f"ZIP      : {ZIP_PATH}")
    print(f"Metadata : {METADATA_PATH}")
    print()
    print("=== V4 QUEBEC REQ DOWNLOAD SUCCESS ===")


if __name__ == "__main__":
    main()