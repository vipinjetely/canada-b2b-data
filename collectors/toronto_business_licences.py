from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

import requests


RESOURCE_ID = "169e90ba-3ae0-43dd-8b2f-919e87002f50"

DOWNLOAD_URL = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/"
    f"datastore/dump/{RESOURCE_ID}"
)

OUTPUT_DIR = Path("data/raw/v2")
OUTPUT_FILE = OUTPUT_DIR / "toronto_business_licences.csv"
METADATA_FILE = OUTPUT_DIR / "toronto_business_licences_metadata.json"


def sha256_file(path):
    digest = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading Toronto business licences...")

    collected_at = datetime.now(timezone.utc)

    with requests.get(
        DOWNLOAD_URL,
        stream=True,
        timeout=180,
    ) as response:
        response.raise_for_status()

        with OUTPUT_FILE.open("wb") as f:
            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    f.write(chunk)

        last_modified = response.headers.get("Last-Modified")

    size = OUTPUT_FILE.stat().st_size
    checksum = sha256_file(OUTPUT_FILE)

    metadata = {
        "source_key": "toronto_business_licences",
        "resource_id": RESOURCE_ID,
        "download_url": DOWNLOAD_URL,
        "collected_at_utc": collected_at.isoformat(),
        "http_last_modified": last_modified,
        "bytes": size,
        "sha256": checksum,
    }

    METADATA_FILE.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print("\n=== TORONTO DOWNLOAD COMPLETE ===")
    print(f"File: {OUTPUT_FILE}")
    print(f"Bytes: {size:,}")
    print(f"Last-Modified: {last_modified}")
    print(f"SHA-256: {checksum}")
    print(f"Metadata: {METADATA_FILE}")


if __name__ == "__main__":
    main()