from pathlib import Path
import json
import re
import unicodedata

import pandas as pd


INPUT_PATH = Path("data/raw/v2/corporations_canada_active.csv")
METADATA_PATH = Path("data/raw/v2/corporations_canada_metadata.json")
OUTPUT_PATH = Path("data/processed/v2/corporations_canada_normalized.csv")


COLUMN_MAP = {
    "Corporation number": "federal_corporation_number",
    "Business number (BN)": "business_number",
    "Corporate name - form 1": "legal_name",
    "Corporate name - form 2": "operating_name",
    "Governing legislation": "governing_legislation",
    "Status": "status",
    "Status Detail": "status_detail",
    "Anniversary date": "anniversary_date",
    "Year of last annual filing": "last_annual_filing_year",
    "Date of last annual meeting": "last_annual_meeting_date",
    "Street": "street",
    "Street 2": "street_2",
    "City/town": "city",
    "Province/territitory": "province",
    "Country": "country",
    "Postal code": "postal_code",
    "Minimum number of directors": "minimum_directors",
    "Maximum number of directors": "maximum_directors",
}

# Correct source spelling.
COLUMN_MAP["Province/territory"] = COLUMN_MAP.pop("Province/territitory")


def normalize_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def normalized_name(value):
    """Create a conservative name key for later entity resolution."""
    if pd.isna(value):
        return pd.NA

    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    text = text.upper().strip()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text or pd.NA


def normalize_dataset() -> None:
    print("Reading fresh Corporations Canada V2 dataset...")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {INPUT_PATH}")

    if not METADATA_PATH.exists():
        raise FileNotFoundError(f"Metadata not found: {METADATA_PATH}")

    metadata = json.loads(
        METADATA_PATH.read_text(encoding="utf-8")
    )

    collected_at = metadata.get("collected_at_utc")
    source_updated_at = metadata.get("http_last_modified")
    source_checksum = metadata.get("sha256")

    if not collected_at:
        raise ValueError("Collection timestamp missing from metadata.")

    if not source_checksum:
        raise ValueError("SHA-256 checksum missing from metadata.")

    df = pd.read_csv(
        INPUT_PATH,
        dtype="string",
        low_memory=False,
    )

    missing_columns = set(COLUMN_MAP) - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Expected columns missing: {sorted(missing_columns)}"
        )

    df = df.rename(columns=COLUMN_MAP)
    df = df[list(COLUMN_MAP.values())].copy()

    for column in df.columns:
        df[column] = normalize_text(df[column])

    df["business_number"] = df["business_number"].str.replace(
        r"\.0$", "",
        regex=True,
    )

    df["postal_code"] = (
        df["postal_code"]
        .str.upper()
        .str.replace(" ", "", regex=False)
    )

    df["province"] = df["province"].str.upper()
    df["country"] = df["country"].str.upper()

    # Conservative keys for later cross-source entity resolution.
    df["normalized_legal_name"] = df["legal_name"].map(normalized_name)

    df["normalized_city"] = (
        df["city"]
        .str.upper()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # Source/provenance metadata.
    df["source_key"] = "corporations_canada"
    df["source_record_id"] = df["federal_corporation_number"]
    df["collected_at_utc"] = collected_at
    df["source_updated_at"] = source_updated_at
    df["source_sha256"] = source_checksum

    # Basic validation.
    if df["federal_corporation_number"].isna().any():
        raise ValueError("Missing federal corporation numbers detected.")

    if df["federal_corporation_number"].duplicated().any():
        raise ValueError("Duplicate federal corporation numbers detected.")

    if df["legal_name"].isna().any():
        raise ValueError("Missing legal business names detected.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(OUTPUT_PATH, index=False)

    print("V2 normalization completed.")
    print(f"Normalized rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")
    print(f"Collected at: {collected_at}")
    print(f"Source updated at: {source_updated_at}")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    normalize_dataset()