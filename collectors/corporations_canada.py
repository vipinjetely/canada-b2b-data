from pathlib import Path

import requests


DATA_URL = (
    "https://d4bf66bykfyaf.cloudfront.net/"
    "corporations-active-cbca-en.csv"
)

OUTPUT_PATH = Path("data/raw/corporations_canada_active.csv")


def download_dataset() -> None:
    """Download the official Corporations Canada active business dataset."""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Downloading Corporations Canada dataset...")

    response = requests.get(DATA_URL, timeout=60)
    response.raise_for_status()

    OUTPUT_PATH.write_bytes(response.content)

    print(f"Saved dataset to: {OUTPUT_PATH}")
    print(f"Downloaded size: {len(response.content):,} bytes")


if __name__ == "__main__":
    download_dataset()