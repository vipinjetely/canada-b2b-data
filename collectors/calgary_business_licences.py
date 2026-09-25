from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests


API_URL = "https://data.calgary.ca/resource/vdjc-pybd.json"

RAW_DIR = Path("data/raw/v2")
RAW_FILE = RAW_DIR / "calgary_business_licences.json"
METADATA_FILE = RAW_DIR / "calgary_business_licences_metadata.json"

PAGE_SIZE = 50_000
TIMEOUT_SECONDS = 120


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def collect() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    collected_at = datetime.now(timezone.utc)

    print("Collecting Calgary business licences...")

    all_records: list[dict] = []
    offset = 0

    while True:
        params = {
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$order": "getbusid",
        }

        response = requests.get(
            API_URL,
            params=params,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        batch = response.json()

        if not isinstance(batch, list):
            raise RuntimeError(
                "Unexpected Calgary API response: expected a JSON list."
            )

        all_records.extend(batch)

        print(
            f"Fetched {len(batch):,} records "
            f"(total {len(all_records):,})"
        )

        if len(batch) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    if not all_records:
        raise RuntimeError("Calgary API returned zero records.")

    with RAW_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            all_records,
            f,
            ensure_ascii=False,
            indent=2,
        )

    checksum = sha256_file(RAW_FILE)

    status_counts: dict[str, int] = {}

    for record in all_records:
        status = str(record.get("jobstatusdesc") or "").strip()
        status = status or "<blank>"
        status_counts[status] = status_counts.get(status, 0) + 1

    metadata = {
        "source_key": "calgary_business_licences",
        "source_name": "City of Calgary Business Licences",
        "source_url": API_URL,
        "dataset_id": "vdjc-pybd",
        "collected_at_utc": collected_at.isoformat(),
        "record_count": len(all_records),
        "sha256": checksum,
        "status_counts": status_counts,
    }

    with METADATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            metadata,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=== CALGARY COLLECTION ===")
    print(f"Records: {len(all_records):,}")
    print(f"SHA256: {checksum}")
    print(f"Collected at: {collected_at.isoformat()}")
    print(f"Raw file: {RAW_FILE}")
    print(f"Metadata: {METADATA_FILE}")

    print()
    print("Licence statuses:")

    for status, count in sorted(
        status_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"  {status}: {count:,}")


if __name__ == "__main__":
    collect()