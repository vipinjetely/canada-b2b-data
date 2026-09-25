from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

import requests


API_URL = (
    "https://data.edmonton.ca/resource/"
    "qhi4-bdpu.json"
)

OUT_DIR = Path("data/raw/v2")
OUT_FILE = OUT_DIR / "edmonton_business_licences.json"
META_FILE = OUT_DIR / "edmonton_business_licences_metadata.json"

PAGE_SIZE = 50000


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = []
    offset = 0

    print("Downloading Edmonton business licences...")

    while True:
        response = requests.get(
            API_URL,
            params={
                "$limit": PAGE_SIZE,
                "$offset": offset,
                "$order": "externalid",
            },
            timeout=120,
        )
        response.raise_for_status()

        rows = response.json()

        if not rows:
            break

        all_rows.extend(rows)

        print(
            f"Downloaded: {len(all_rows):,} records"
        )

        if len(rows) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    raw_bytes = json.dumps(
        all_rows,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    OUT_FILE.write_bytes(raw_bytes)

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    collected_at = datetime.now(timezone.utc)

    metadata = {
        "source_key": "edmonton_business_licences",
        "source_url": API_URL,
        "dataset_id": "qhi4-bdpu",
        "collected_at_utc": collected_at.isoformat(),
        "record_count": len(all_rows),
        "sha256": sha256,
    }

    META_FILE.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print("\n=== EDMONTON COLLECTION ===")
    print(f"Records: {len(all_rows):,}")
    print(f"SHA256: {sha256}")
    print(f"Raw: {OUT_FILE}")
    print(f"Metadata: {META_FILE}")


if __name__ == "__main__":
    main()