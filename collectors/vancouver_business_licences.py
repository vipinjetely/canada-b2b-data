from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import requests


SOURCE_KEY = "vancouver_business_licences"

DATA_URL = (
    "https://opendata.vancouver.ca/api/explore/v2.1/catalog/"
    "datasets/business-licences/exports/csv"
)

OUTPUT_PATH = Path(
    "data/raw/v2/vancouver_business_licences.csv"
)

METADATA_PATH = Path(
    "data/raw/v2/vancouver_business_licences_metadata.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def download_dataset() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    collected_at = datetime.now(timezone.utc)

    print("Downloading Vancouver business licences...")
    print(f"Source: {DATA_URL}")

    temp_path = OUTPUT_PATH.with_suffix(".tmp")

    try:
        with requests.get(
            DATA_URL,
            params={
                "lang": "en",
                "timezone": "UTC",
                "use_labels": "true",
                "delimiter": ",",
            },
            timeout=(15, 180),
            stream=True,
            headers={
                "User-Agent": "Canada-B2B-Data-Automation/2.0"
            },
        ) as response:

            response.raise_for_status()

            content_type = response.headers.get("Content-Type")
            last_modified = response.headers.get("Last-Modified")
            etag = response.headers.get("ETag")

            bytes_downloaded = 0

            with temp_path.open("wb") as file:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        file.write(chunk)
                        bytes_downloaded += len(chunk)

        if bytes_downloaded == 0:
            raise RuntimeError(
                "Vancouver dataset download returned an empty file."
            )

        temp_path.replace(OUTPUT_PATH)

    finally:
        if temp_path.exists():
            temp_path.unlink()

    checksum = sha256_file(OUTPUT_PATH)

    metadata = {
        "source_key": SOURCE_KEY,
        "source_url": DATA_URL,
        "collected_at_utc": collected_at.isoformat(),
        "http_last_modified": last_modified,
        "http_etag": etag,
        "http_content_type": content_type,
        "downloaded_bytes": bytes_downloaded,
        "sha256": checksum,
        "output_path": str(OUTPUT_PATH),
    }

    METADATA_PATH.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print("Download completed successfully.")
    print(f"Dataset: {OUTPUT_PATH}")
    print(f"Metadata: {METADATA_PATH}")
    print(f"Downloaded: {bytes_downloaded:,} bytes")
    print(f"HTTP Last-Modified: {last_modified}")
    print(f"SHA-256: {checksum}")


if __name__ == "__main__":
    download_dataset()