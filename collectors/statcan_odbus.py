from pathlib import Path
from zipfile import ZipFile

import requests


DATA_URL = (
    "https://www150.statcan.gc.ca/n1/pub/"
    "21-26-0003/2023001/ODBus_2023.zip"
)

ZIP_PATH = Path("data/external/ODBus_2023.zip")
EXTRACT_PATH = Path("data/external/odbus")


def download_odbus() -> None:
    """Download and extract Statistics Canada's Open Database of Businesses."""

    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXTRACT_PATH.mkdir(parents=True, exist_ok=True)

    print("Downloading Statistics Canada ODBus...")

    with requests.get(DATA_URL, stream=True, timeout=120) as response:
        response.raise_for_status()

        with ZIP_PATH.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)

    print(f"Downloaded: {ZIP_PATH}")
    print(f"Size: {ZIP_PATH.stat().st_size:,} bytes")

    print("Extracting dataset...")

    with ZipFile(ZIP_PATH, "r") as archive:
        archive.extractall(EXTRACT_PATH)

    print(f"Extracted to: {EXTRACT_PATH}")

    print("\nFiles:")
    for path in sorted(EXTRACT_PATH.rglob("*")):
        if path.is_file():
            print(f" - {path}")


if __name__ == "__main__":
    download_odbus()