from datetime import datetime, timezone
from pathlib import Path
import json
import hashlib

import requests


DATA_URL = (
    "https://d4bf66bykfyaf.cloudfront.net/"
    "corporations-active-cbca-en.csv"
)

OUTPUT_PATH = Path("data/raw/v2/corporations_canada_active.csv")
METADATA_PATH = Path("data/raw/v2/corporations_canada_metadata.json")

SOURCE_KEY = "corporations_canada"


def sha256_file(path: Path) -> str:
    """Return SHA-256 checksum for a downloaded file."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def download_dataset() -> None:
    """
    Download the current Corporations Canada active corporation dataset
    and preserve collection metadata for freshness and reproducibility.
    """

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    collected_at = datetime.now(timezone.utc)

    print("Downloading fresh Corporations Canada dataset...")
    print(f"Source: {DATA_URL}")

    with requests.get(
        DATA_URL,
        timeout=(15, 180),
        stream=True,
        headers={"User-Agent": "Canada-B2B-Data-Automation/2.0"},
    ) as response:
        response.raise_for_status()

        content_type = response.headers.get("Content-Type")
        content_length = response.headers.get("Content-Length")
        last_modified = response.headers.get("Last-Modified")
        etag = response.headers.get("ETag")

        temp_path = OUTPUT_PATH.with_suffix(".tmp")

        bytes_downloaded = 0

        try:
            with temp_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)
                        bytes_downloaded += len(chunk)

            if bytes_downloaded == 0:
                raise RuntimeError("Downloaded dataset is empty.")

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
        "http_content_length": content_length,
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