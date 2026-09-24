from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


INPUT_PATH = Path("data/external/odbus/ODBus_v1/ODBus_v1.csv")
OUTPUT_PATH = Path("data/processed/statcan_odbus_normalized.csv")


KEEP_COLUMNS = [
    "idx",
    "business_name",
    "alt_business_name",
    "business_sector",
    "business_subsector",
    "business_description",
    "business_id_no",
    "derived_NAICS",
    "source_NAICS_primary",
    "NAICS_descr",
    "latitude",
    "longitude",
    "full_address",
    "postal_code",
    "city",
    "prov_terr",
    "total_no_employees",
    "status",
    "provider",
]


def clean_text(series: pd.Series) -> pd.Series:
    """Normalize text and convert ODBus missing-value markers to NA."""
    series = series.astype("string").str.strip()
    return series.replace({"..": pd.NA, "": pd.NA})


def normalize_name(series: pd.Series) -> pd.Series:
    """Create a conservative matching key from a business name."""
    return (
        clean_text(series)
        .str.upper()
        .str.replace(r"[^A-Z0-9]+", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def normalize_dataset() -> None:
    print("Reading Statistics Canada ODBus...")

    df = pd.read_csv(INPUT_PATH, dtype=str, low_memory=False)

    missing = set(KEEP_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing expected ODBus columns: {sorted(missing)}")

    df = df[KEEP_COLUMNS].copy()

    text_columns = [
        column
        for column in KEEP_COLUMNS
        if column not in {"latitude", "longitude"}
    ]

    for column in text_columns:
        df[column] = clean_text(df[column])

    df["postal_code"] = (
        df["postal_code"]
        .str.upper()
        .str.replace(" ", "", regex=False)
    )

    df["province"] = df["prov_terr"].str.upper()

    df["business_name_match"] = normalize_name(df["business_name"])

    df["source"] = "Statistics Canada ODBus"
    df["source_record_id"] = df["idx"]
    df["collected_at_utc"] = datetime.now(timezone.utc).isoformat()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Normalized ODBus rows: {len(df):,}")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    normalize_dataset()