from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


RAW_FILE = Path("data/raw/v2/calgary_business_licences.json")
METADATA_FILE = Path("data/raw/v2/calgary_business_licences_metadata.json")
OUTPUT_FILE = Path("data/processed/v2/calgary_business_licences_normalized.csv")

SOURCE_KEY = "calgary_business_licences"

CURRENT_STATUSES = {
    "LICENSED",
    "RENEWAL LICENSED",
    "PENDING RENEWAL",
    "RENEWAL INVOICED",
    "RENEWAL NOTIFICATION SENT",
}

INVALID_NAMES = {
    "",
    "NONE",
    "NULL",
    "N/A",
    "NA",
    "<NA>",
    "REDACTED",
    "<REDACTED FOR PRIVACY>",
}


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""

    value = str(value).strip().upper()
    value = re.sub(r"[^A-Z0-9]+", "", value)
    return value


def clean_string(value):
    if pd.isna(value):
        return pd.NA

    value = str(value).strip()

    if not value:
        return pd.NA

    return value


def main() -> None:
    print("Reading Calgary raw data...")

    with RAW_FILE.open("r", encoding="utf-8") as f:
        records = json.load(f)

    with METADATA_FILE.open("r", encoding="utf-8") as f:
        metadata = json.load(f)

    raw_count = len(records)

    df = pd.DataFrame(records)

    print(f"Raw records: {raw_count:,}")

    required_columns = [
        "getbusid",
        "tradename",
        "homeoccind",
        "address",
        "comdistcd",
        "comdistnm",
        "licencetypes",
        "first_iss_dt",
        "exp_dt",
        "jobstatusdesc",
        "globalid",
    ]

    for column in required_columns:
        if column not in df.columns:
            df[column] = pd.NA

    df["source_record_id"] = df["getbusid"].map(clean_string)
    df["legal_name"] = df["tradename"].map(clean_string)

    name_upper = (
        df["legal_name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df = df[
        df["source_record_id"].notna()
        & ~name_upper.isin(INVALID_NAMES)
    ].copy()

    df["status"] = (
        df["jobstatusdesc"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["first_issue_date"] = pd.to_datetime(
        df["first_iss_dt"],
        errors="coerce",
        utc=True,
    )

    df["expiry_date"] = pd.to_datetime(
        df["exp_dt"],
        errors="coerce",
        utc=True,
    )

    reference_time = pd.to_datetime(
        metadata["collected_at_utc"],
        utc=True,
    )

    current = df[
        df["status"].isin(CURRENT_STATUSES)
        & (
            df["expiry_date"].isna()
            | (df["expiry_date"] >= reference_time)
        )
    ].copy()

    current = (
        current
        .sort_values(
            ["source_record_id", "expiry_date"],
            na_position="first",
        )
        .drop_duplicates(
            subset=["source_record_id"],
            keep="last",
        )
        .copy()
    )

    current["operating_name"] = current["legal_name"]
    current["normalized_legal_name"] = current["legal_name"].map(normalize_text)

    current["street"] = current["address"].map(clean_string)

    # Calgary flags home occupations explicitly.
    # Do not publish/store their street address in the canonical dataset.
    home_mask = (
        current["homeoccind"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .eq("Y")
    )

    current.loc[home_mask, "street"] = pd.NA

    # Also suppress explicit privacy/redaction placeholders.
    privacy_mask = (
        current["street"]
        .fillna("")
        .astype(str)
        .str.contains(
            r"HOME\s*BASED|REDACTED|PRIVACY",
            case=False,
            regex=True,
        )
    )

    current.loc[privacy_mask, "street"] = pd.NA

    current["normalized_street"] = current["street"].map(normalize_text)

    current["city"] = "Calgary"
    current["normalized_city"] = "CALGARY"
    current["province"] = "AB"
    current["country"] = "CA"

    current["postal_code"] = pd.NA

    current["industry"] = current["licencetypes"].map(clean_string)
    current["community_code"] = current["comdistcd"].map(clean_string)
    current["community_name"] = current["comdistnm"].map(clean_string)

    current["source_key"] = SOURCE_KEY
    current["collected_at_utc"] = metadata["collected_at_utc"]
    current["source_sha256"] = metadata["sha256"]

    age = reference_time - current["first_issue_date"]

    current["is_new_1d"] = (
        current["first_issue_date"].notna()
        & (age >= pd.Timedelta(0))
        & (age <= pd.Timedelta(days=1))
    )

    current["is_new_7d"] = (
        current["first_issue_date"].notna()
        & (age >= pd.Timedelta(0))
        & (age <= pd.Timedelta(days=7))
    )

    current["is_new_30d"] = (
        current["first_issue_date"].notna()
        & (age >= pd.Timedelta(0))
        & (age <= pd.Timedelta(days=30))
    )

    output_columns = [
        "source_record_id",
        "legal_name",
        "operating_name",
        "normalized_legal_name",
        "street",
        "normalized_street",
        "city",
        "normalized_city",
        "province",
        "country",
        "postal_code",
        "industry",
        "community_code",
        "community_name",
        "status",
        "first_issue_date",
        "expiry_date",
        "homeoccind",
        "globalid",
        "source_key",
        "collected_at_utc",
        "source_sha256",
        "is_new_1d",
        "is_new_7d",
        "is_new_30d",
    ]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    current[output_columns].to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print("=== CALGARY NORMALIZATION ===")
    print(f"Raw records: {raw_count:,}")
    print(f"Current unique licences: {len(current):,}")
    print(
        f"Unique normalized names: "
        f"{current['normalized_legal_name'].nunique():,}"
    )
    print(
        f"With visible street address: "
        f"{current['street'].notna().sum():,}"
    )
    print(
        f"Home occupation addresses suppressed: "
        f"{home_mask.sum():,}"
    )
    print(f"New 1 day: {current['is_new_1d'].sum():,}")
    print(f"New 7 days: {current['is_new_7d'].sum():,}")
    print(f"New 30 days: {current['is_new_30d'].sum():,}")
    print(f"Reference time: {reference_time}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()