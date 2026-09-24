from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


INPUT_PATH = Path("data/raw/corporations_canada_active.csv")
OUTPUT_PATH = Path("data/processed/corporations_canada_normalized.csv")


COLUMN_MAP = {
    "Corporation number": "corporation_number",
    "Business number (BN)": "business_number",
    "Corporate name - form 1": "business_name",
    "Corporate name - form 2": "business_name_alt",
    "Governing legislation": "governing_legislation",
    "Status": "status",
    "Status Detail": "status_detail",
    "Anniversary date": "anniversary_date",
    "Year of last annual filing": "last_annual_filing_year",
    "Date of last annual meeting": "last_annual_meeting_date",
    "Street": "street",
    "Street 2": "street_2",
    "City/town": "city",
    "Province/territory": "province",
    "Country": "country",
    "Postal code": "postal_code",
    "Minimum number of directors": "minimum_directors",
    "Maximum number of directors": "maximum_directors",
}


def normalize_text(series: pd.Series) -> pd.Series:
    """Trim whitespace while preserving missing values."""
    return series.astype("string").str.strip()


def normalize_dataset() -> None:
    """Normalize the raw Corporations Canada dataset."""

    print("Reading raw Corporations Canada dataset...")

    df = pd.read_csv(
        INPUT_PATH,
        dtype={
            "Corporation number": "string",
            "Business number (BN)": "string",
        },
        low_memory=False,
    )

    missing_columns = set(COLUMN_MAP) - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Expected columns missing from source dataset: "
            f"{sorted(missing_columns)}"
        )

    df = df.rename(columns=COLUMN_MAP)
    df = df[list(COLUMN_MAP.values())].copy()

    text_columns = [
        "corporation_number",
        "business_number",
        "business_name",
        "business_name_alt",
        "governing_legislation",
        "status",
        "status_detail",
        "street",
        "street_2",
        "city",
        "province",
        "country",
        "postal_code",
    ]

    for column in text_columns:
        df[column] = normalize_text(df[column])

    # Remove the ".0" representation that may result from numeric-looking BNs.
    df["business_number"] = df["business_number"].str.replace(
        r"\.0$", "", regex=True
    )

    # Standardize postal codes for matching/deduplication.
    df["postal_code"] = (
        df["postal_code"]
        .str.upper()
        .str.replace(" ", "", regex=False)
    )

    # Add provenance metadata.
    df["source"] = "Corporations Canada"
    df["source_record_id"] = df["corporation_number"]
    df["collected_at_utc"] = datetime.now(timezone.utc).isoformat()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Normalized rows: {len(df):,}")
    print(f"Saved normalized dataset to: {OUTPUT_PATH}")
    print(f"Columns: {len(df.columns)}")


if __name__ == "__main__":
    normalize_dataset()