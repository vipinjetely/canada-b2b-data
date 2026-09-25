from datetime import datetime, timezone
from pathlib import Path
import json
import re
import unicodedata

import pandas as pd


INPUT_PATH = Path(
    "data/raw/v2/vancouver_business_licences.csv"
)

METADATA_PATH = Path(
    "data/raw/v2/vancouver_business_licences_metadata.json"
)

OUTPUT_PATH = Path(
    "data/processed/v2/vancouver_business_licences_normalized.csv"
)

SOURCE_KEY = "vancouver_business_licences"


def clean_text(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.strip()
        .replace("", pd.NA)
    )


def normalize_name(value):
    if pd.isna(value):
        return pd.NA

    text = unicodedata.normalize("NFKD", str(value))

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = text.upper().strip()

    text = re.sub(
        r"[^A-Z0-9]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text or pd.NA


def employee_bucket(value):
    if pd.isna(value):
        return pd.NA

    try:
        number = int(float(str(value).strip()))
    except (ValueError, TypeError):
        return pd.NA

    # Zero is preserved separately rather than pretending
    # that it represents 1-4 employees.
    if number == 0:
        return "0"

    if 1 <= number <= 4:
        return "1-4"

    if number <= 9:
        return "5-9"

    if number <= 19:
        return "10-19"

    if number <= 49:
        return "20-49"

    if number <= 99:
        return "50-99"

    if number <= 199:
        return "100-199"

    if number <= 499:
        return "200-499"

    if number <= 999:
        return "500-999"

    return "1,000+"


def normalize_dataset() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {INPUT_PATH}"
        )

    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Metadata not found: {METADATA_PATH}"
        )

    metadata = json.loads(
        METADATA_PATH.read_text(
            encoding="utf-8"
        )
    )

    collected_at = metadata.get(
        "collected_at_utc"
    )

    source_checksum = metadata.get(
        "sha256"
    )

    if not collected_at:
        raise ValueError(
            "Collection timestamp missing."
        )

    if not source_checksum:
        raise ValueError(
            "Source checksum missing."
        )

    print(
        "Reading Vancouver business licences..."
    )

    df = pd.read_csv(
        INPUT_PATH,
        dtype="string",
        low_memory=False,
    )

    required_columns = [
        "FOLDERYEAR",
        "LicenceRSN",
        "LicenceNumber",
        "LicenceRevisionNumber",
        "BusinessName",
        "BusinessTradeName",
        "Status",
        "IssuedDate",
        "ExpiredDate",
        "BusinessType",
        "BusinessSubType",
        "Unit",
        "UnitType",
        "House",
        "Street",
        "City",
        "Province",
        "Country",
        "PostalCode",
        "LocalArea",
        "NumberofEmployees",
        "ExtractDate",
    ]

    missing = (
        set(required_columns)
        - set(df.columns)
    )

    if missing:
        raise ValueError(
            "Expected columns missing: "
            f"{sorted(missing)}"
        )

    df = df[required_columns].copy()

    for column in required_columns:
        df[column] = clean_text(
            df[column]
        )

    raw_rows = len(df)

    # Current operational records only.
    df = df[
        df["Status"].eq("Issued")
    ].copy()

    issued_rows = len(df)

    # Use legal name first and trade name
    # only when legal name is unavailable.
    df["display_name"] = (
        df["BusinessName"]
        .fillna(df["BusinessTradeName"])
        .str.strip()
    )

    df = df[
        df["display_name"].notna()
        & df["display_name"].ne("")
    ].copy()

    named_issued_rows = len(df)

    # Parse dates explicitly.
    df["issued_at"] = pd.to_datetime(
        df["IssuedDate"],
        errors="coerce",
        utc=True,
    )

    df["expired_at"] = pd.to_datetime(
        df["ExpiredDate"],
        errors="coerce",
        utc=True,
    )

    df["extract_at"] = pd.to_datetime(
        df["ExtractDate"],
        errors="coerce",
        utc=True,
    )

    now_utc = pd.Timestamp.now(
        tz="UTC"
    )

    df["is_future_issued"] = (
        df["issued_at"].notna()
        & (df["issued_at"] > now_utc)
    )

    # Future-effective records remain preserved
    # but are not considered current usable rows.
    df["is_current_usable"] = (
        ~df["is_future_issued"]
    )

    df["normalized_business_name"] = (
        df["display_name"].map(
            normalize_name
        )
    )

    df["normalized_trade_name"] = (
        df["BusinessTradeName"].map(
            normalize_name
        )
    )

    df["postal_code"] = (
        df["PostalCode"]
        .str.upper()
        .str.replace(
            " ",
            "",
            regex=False,
        )
    )

    df["city"] = (
        df["City"]
        .str.upper()
        .str.replace(
            r"\s+",
            " ",
            regex=True,
        )
        .str.strip()
    )

    df["province"] = (
        df["Province"]
        .str.upper()
        .str.strip()
    )

    df["country"] = (
        df["Country"]
        .str.upper()
        .str.strip()
    )

    df["employee_count"] = pd.to_numeric(
        df["NumberofEmployees"],
        errors="coerce",
    ).astype("Int64")

    df["employee_size_bucket"] = (
        df["NumberofEmployees"].map(
            employee_bucket
        )
    )

    # Construct a standardized street string
    # without inventing missing components.
    address_parts = [
        df["Unit"].fillna(""),
        df["UnitType"].fillna(""),
        df["House"].fillna(""),
        df["Street"].fillna(""),
    ]

    df["street_address"] = (
        address_parts[0]
        + " "
        + address_parts[1]
        + " "
        + address_parts[2]
        + " "
        + address_parts[3]
    )

    df["street_address"] = (
        df["street_address"]
        .str.replace(
            r"\s+",
            " ",
            regex=True,
        )
        .str.strip()
        .replace("", pd.NA)
    )

    df["source_key"] = SOURCE_KEY

    df["source_record_id"] = (
        df["LicenceRSN"]
    )

    df["collected_at_utc"] = (
        collected_at
    )

    df["source_sha256"] = (
        source_checksum
    )

    output_columns = [
        "source_record_id",
        "LicenceRSN",
        "LicenceNumber",
        "LicenceRevisionNumber",
        "FOLDERYEAR",
        "BusinessName",
        "BusinessTradeName",
        "display_name",
        "normalized_business_name",
        "normalized_trade_name",
        "Status",
        "issued_at",
        "expired_at",
        "extract_at",
        "is_future_issued",
        "is_current_usable",
        "BusinessType",
        "BusinessSubType",
        "street_address",
        "city",
        "province",
        "country",
        "postal_code",
        "LocalArea",
        "employee_count",
        "employee_size_bucket",
        "source_key",
        "collected_at_utc",
        "source_sha256",
    ]

    df = df[
        output_columns
    ].copy()

    if df["source_record_id"].isna().any():
        raise ValueError(
            "Missing LicenceRSN detected."
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    usable = int(
        df["is_current_usable"].sum()
    )

    future = int(
        df["is_future_issued"].sum()
    )

    print(
        "Vancouver normalization completed."
    )
    print(
        f"Raw rows: {raw_rows:,}"
    )
    print(
        f"Issued rows: {issued_rows:,}"
    )
    print(
        "Issued + named rows: "
        f"{named_issued_rows:,}"
    )
    print(
        f"Current usable rows: {usable:,}"
    )
    print(
        f"Future-issued rows: {future:,}"
    )
    print(
        "Unique normalized names: "
        f"{df['normalized_business_name'].nunique():,}"
    )

    print("\nEmployee-size buckets:")

    print(
        df["employee_size_bucket"]
        .fillna("<NULL>")
        .value_counts()
        .to_string()
    )

    print(
        f"\nSaved to: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    normalize_dataset()