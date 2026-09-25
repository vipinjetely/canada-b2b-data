from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests


DOWNLOAD_URL = (
    "https://www.donneesquebec.ca/recherche/dataset/"
    "755b45d6-7aee-46df-a216-748a0191c79f/resource/"
    "32f6ec46-85fd-45e9-945b-965d9235840a/download/"
    "liste-licences-actives.zip"
)

RAW_DIR = Path("data/raw/v2")

DOWNLOAD_FILE = RAW_DIR / "quebec_rbq_active_licences.zip"

EXTRACT_DIR = (
    RAW_DIR / "quebec_rbq_active_licences"
)

METADATA_FILE = (
    RAW_DIR / "quebec_rbq_active_licences_metadata.json"
)

CHUNK_SIZE = 1024 * 1024
TIMEOUT = 180


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def inspect_csv(path: Path):
    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    ]

    last_error = None

    for encoding in encodings:
        try:
            with path.open(
                "r",
                encoding=encoding,
                newline="",
            ) as f:

                sample = f.read(65536)

                if not sample:
                    raise RuntimeError(
                        "Extracted RBQ CSV is empty."
                    )

                try:
                    dialect = csv.Sniffer().sniff(
                        sample,
                        delimiters=",;\t|",
                    )
                    delimiter = dialect.delimiter
                except csv.Error:
                    delimiter = ","

                f.seek(0)

                reader = csv.reader(
                    f,
                    delimiter=delimiter,
                )

                header = next(reader)

                row_count = sum(1 for _ in reader)

                return (
                    encoding,
                    delimiter,
                    header,
                    row_count,
                )

        except UnicodeDecodeError as exc:
            last_error = exc

    raise RuntimeError(
        "Could not decode extracted RBQ CSV."
    ) from last_error


def main() -> None:
    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    EXTRACT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "Downloading Québec RBQ active licences..."
    )

    headers = {
        "User-Agent": "canada-b2b-data/2.0"
    }

    with requests.get(
        DOWNLOAD_URL,
        headers=headers,
        stream=True,
        timeout=TIMEOUT,
    ) as response:

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type"
        )

        last_modified = response.headers.get(
            "Last-Modified"
        )

        with DOWNLOAD_FILE.open("wb") as f:
            for chunk in response.iter_content(
                chunk_size=CHUNK_SIZE
            ):
                if chunk:
                    f.write(chunk)

    file_size = DOWNLOAD_FILE.stat().st_size
    checksum = sha256_file(DOWNLOAD_FILE)

    collected_at = datetime.now(
        timezone.utc
    ).isoformat()

    print(f"Downloaded bytes: {file_size:,}")
    print(f"Content-Type: {content_type}")
    print(f"Last-Modified: {last_modified}")
    print(f"SHA256: {checksum}")

    print()
    print("Checking actual file format...")

    if not zipfile.is_zipfile(DOWNLOAD_FILE):
        raise RuntimeError(
            "Downloaded RBQ resource is not a valid ZIP archive."
        )

    print("Actual format: ZIP")

    print()
    print("Extracting archive...")

    with zipfile.ZipFile(
        DOWNLOAD_FILE,
        "r",
    ) as archive:

        members = archive.namelist()

        print("Archive members:")

        for member in members:
            print(f"  {member}")

        archive.extractall(EXTRACT_DIR)

    csv_files = list(
        EXTRACT_DIR.rglob("*.csv")
    )

    if not csv_files:
        raise RuntimeError(
            "No CSV file found inside RBQ archive."
        )

    print()
    print(
        f"CSV files found: {len(csv_files)}"
    )

    total_rows = 0
    inspected_files = []

    for csv_file in csv_files:

        print()
        print(
            f"Inspecting: {csv_file.name}"
        )

        (
            encoding,
            delimiter,
            columns,
            row_count,
        ) = inspect_csv(csv_file)

        total_rows += row_count

        print(
            f"Encoding: {encoding}"
        )

        print(
            f"Delimiter: {repr(delimiter)}"
        )

        print(
            f"Rows: {row_count:,}"
        )

        print(
            f"Columns: {len(columns)}"
        )

        print()
        print("Column names:")

        for index, column in enumerate(
            columns,
            start=1,
        ):
            print(
                f"{index:02d}. {column}"
            )

        inspected_files.append(
            {
                "file": str(
                    csv_file.relative_to(RAW_DIR)
                ),
                "encoding": encoding,
                "delimiter": delimiter,
                "row_count": row_count,
                "columns": columns,
            }
        )

    metadata = {
        "source_key":
            "quebec_rbq_active_licences",

        "source_name":
            (
                "Régie du bâtiment du Québec - "
                "Liste des licences actives"
            ),

        "source_url":
            DOWNLOAD_URL,

        "collected_at_utc":
            collected_at,

        "last_modified":
            last_modified,

        "reported_content_type":
            content_type,

        "actual_format":
            "zip",

        "download_bytes":
            file_size,

        "sha256":
            checksum,

        "archive_members":
            members,

        "csv_files":
            inspected_files,

        "total_csv_rows":
            total_rows,
    }

    METADATA_FILE.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        f"Total CSV rows: {total_rows:,}"
    )

    print(
        f"Metadata: {METADATA_FILE}"
    )

    print()
    print(
        "Québec RBQ collection completed."
    )


if __name__ == "__main__":
    main()